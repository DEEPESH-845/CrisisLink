/// ChangeNotifier managing responder state for the Responder App.
///
/// Subscribes to Firebase RTDB streams for dispatch details and call
/// classification, manages unit status transitions, and coordinates
/// GPS tracking via [GpsService].
///
/// Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/emergency_classification.dart';
import '../models/response_unit.dart';
import '../services/fcm_service.dart';
import '../services/gps_service.dart';
import '../services/responder_firebase_service.dart';

/// Central state manager for the Responder App.
///
/// Holds the current dispatch assignment, case context (classification),
/// unit status, and GPS tracking state. Exposes methods for status
/// transitions that enforce the valid transition graph (Property 10).
class ResponderProvider extends ChangeNotifier {
  final ResponderFirebaseService _firebaseService;
  final FcmService _fcmService;
  final GpsService _gpsService;

  ResponderProvider({
    required ResponderFirebaseService firebaseService,
    required FcmService fcmService,
    required GpsService gpsService,
  })  : _firebaseService = firebaseService,
        _fcmService = fcmService,
        _gpsService = gpsService;

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  String? _unitId;
  UnitStatus _unitStatus = UnitStatus.available;
  DispatchDetails? _dispatchDetails;
  EmergencyClassification? _classification;
  bool _isConnected = true;
  bool _isUpdatingStatus = false;

  /// Error message from the last failed status update, if any.
  String? _statusUpdateError;

  // ---------------------------------------------------------------------------
  // Stream subscriptions
  // ---------------------------------------------------------------------------

  final List<StreamSubscription<dynamic>> _subscriptions = [];

  // ---------------------------------------------------------------------------
  // Getters
  // ---------------------------------------------------------------------------

  String? get unitId => _unitId;
  UnitStatus get unitStatus => _unitStatus;
  DispatchDetails? get dispatchDetails => _dispatchDetails;
  EmergencyClassification? get classification => _classification;
  bool get isConnected => _isConnected;
  bool get isUpdatingStatus => _isUpdatingStatus;
  String? get statusUpdateError => _statusUpdateError;
  GpsService get gpsService => _gpsService;

  /// Whether the responder currently has an active dispatch assignment.
  bool get hasActiveDispatch => _dispatchDetails != null;

  /// The next valid status the responder can transition to, or `null` if
  /// no valid transition exists from the current status.
  UnitStatus? get nextValidStatus => validStatusTransitions[_unitStatus];

  // ---------------------------------------------------------------------------
  // Initialization
  // ---------------------------------------------------------------------------

  /// Initialize the responder session for [unitId].
  ///
  /// Subscribes to Firebase RTDB streams for dispatch and status,
  /// registers for FCM push notifications, and starts GPS tracking.
  void initialize(String unitId) {
    _cancelSubscriptions();

    _unitId = unitId;
    _unitStatus = UnitStatus.available;
    _dispatchDetails = null;
    _classification = null;
    _statusUpdateError = null;
    _isUpdatingStatus = false;

    // Subscribe to FCM dispatch notifications.
    _fcmService.subscribeToUnit(unitId);

    // Subscribe to connection state.
    _subscriptions.add(
      _firebaseService.connectionState.listen(
        (connected) {
          _isConnected = connected;
          notifyListeners();
        },
        onError: (_) {
          _isConnected = false;
          notifyListeners();
        },
      ),
    );

    // Subscribe to unit status from Firebase RTDB.
    _subscriptions.add(
      _firebaseService.unitStatusStream(unitId).listen(
        (status) {
          _unitStatus = status;
          notifyListeners();
        },
      ),
    );

    // Subscribe to dispatch details.
    _subscriptions.add(
      _firebaseService.dispatchStream(unitId).listen(
        (details) {
          _dispatchDetails = details;

          // When a new dispatch arrives, subscribe to the call's classification
          // for case context.
          if (details != null && details.callId.isNotEmpty) {
            _subscribeToClassification(details.callId);
          } else {
            _classification = null;
          }

          notifyListeners();
        },
      ),
    );

    // Subscribe to FCM foreground notifications.
    _subscriptions.add(
      _fcmService.onDispatchNotification.listen(
        (notification) {
          // FCM notification received — the RTDB dispatch stream will
          // provide the full details. This listener is here for cases
          // where the RTDB stream hasn't fired yet.
          debugPrint(
            'FCM dispatch notification: ${notification.callId} '
            '${notification.emergencyType} ${notification.severity}',
          );
        },
      ),
    );

    // Start GPS tracking.
    _gpsService.startTracking(unitId);

    notifyListeners();
  }

  /// Subscribe to the classification stream for case context.
  void _subscribeToClassification(String callId) {
    // Remove any existing classification subscription.
    // (We keep it simple — only one call at a time.)
    _subscriptions.add(
      _firebaseService.classificationStream(callId).listen(
        (classification) {
          _classification = classification;
          notifyListeners();
        },
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Status transitions (Property 10)
  // ---------------------------------------------------------------------------

  /// Transition the unit to [newStatus].
  ///
  /// Validates the transition against the allowed graph:
  /// available → dispatched → on_scene → returning → available.
  ///
  /// Returns `true` if the transition succeeded.
  Future<bool> transitionStatus(UnitStatus newStatus) async {
    if (_unitId == null) return false;

    _statusUpdateError = null;
    _isUpdatingStatus = true;
    notifyListeners();

    try {
      final success = await _firebaseService.updateUnitStatus(
        unitId: _unitId!,
        currentStatus: _unitStatus,
        newStatus: newStatus,
      );

      if (!success) {
        _statusUpdateError =
            'Invalid transition: ${_unitStatus.value} → ${newStatus.value}';
      } else {
        // If returning to available, clear the dispatch assignment.
        if (newStatus == UnitStatus.available) {
          await _firebaseService.clearDispatch(_unitId!);
          _dispatchDetails = null;
          _classification = null;
        }
      }

      return success;
    } catch (e) {
      _statusUpdateError = 'Status update failed: $e';
      return false;
    } finally {
      _isUpdatingStatus = false;
      notifyListeners();
    }
  }

  /// Convenience: transition to the next valid status.
  Future<bool> transitionToNext() async {
    final next = nextValidStatus;
    if (next == null) return false;
    return transitionStatus(next);
  }

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  void _cancelSubscriptions() {
    for (final sub in _subscriptions) {
      sub.cancel();
    }
    _subscriptions.clear();
  }

  /// Disconnect from the responder session.
  void disconnect() {
    _gpsService.stopTracking();
    if (_unitId != null) {
      _fcmService.unsubscribeFromUnit(_unitId!);
    }
    _cancelSubscriptions();
    _unitId = null;
    _dispatchDetails = null;
    _classification = null;
    notifyListeners();
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }
}
