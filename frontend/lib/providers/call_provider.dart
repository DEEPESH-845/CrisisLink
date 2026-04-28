/// ChangeNotifier that manages active call state from Firebase RTDB streams.
///
/// Subscribes to all call-level Firebase paths and exposes reactive state
/// for the Operator Dashboard widgets. Handles classification timeout
/// detection (8s), connection state, and subsystem error tracking.
///
/// Requirements: 6.1, 6.2, 6.6, 11.4, 11.6
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/call_session.dart';
import '../models/dispatch_card.dart';
import '../models/emergency_classification.dart';
import '../services/firebase_service.dart';

/// Represents a subsystem error that the operator should be notified about.
class SubsystemError {
  final String subsystem;
  final String message;
  final DateTime occurredAt;

  const SubsystemError({
    required this.subsystem,
    required this.message,
    required this.occurredAt,
  });
}

/// Central state manager for the active call on the Operator Dashboard.
class CallProvider extends ChangeNotifier {
  final FirebaseService _firebaseService;

  CallProvider({required FirebaseService firebaseService})
      : _firebaseService = firebaseService;

  // ---------------------------------------------------------------------------
  // State fields
  // ---------------------------------------------------------------------------

  String? _activeCallId;
  String _transcript = '';
  EmergencyClassification? _classification;
  CallerState? _callerState;
  DispatchCard? _dispatchCard;
  Guidance? _guidance;
  CallStatus _callStatus = CallStatus.active;
  bool _manualOverride = false;
  bool _isConnected = true;

  /// Whether the classification has timed out (> 8 seconds with no result).
  bool _classificationTimedOut = false;

  /// Timestamp when the call was subscribed to (used for timeout detection).
  DateTime? _callStartTime;

  /// Active subsystem errors that the operator should see.
  final List<SubsystemError> _subsystemErrors = [];

  /// Whether a dispatch confirmation is in progress.
  bool _isDispatching = false;

  // ---------------------------------------------------------------------------
  // Stream subscriptions
  // ---------------------------------------------------------------------------

  final List<StreamSubscription<dynamic>> _subscriptions = [];
  Timer? _timeoutTimer;

  // ---------------------------------------------------------------------------
  // Getters
  // ---------------------------------------------------------------------------

  String? get activeCallId => _activeCallId;
  String get transcript => _transcript;
  EmergencyClassification? get classification => _classification;
  CallerState? get callerState => _callerState;
  DispatchCard? get dispatchCard => _dispatchCard;
  Guidance? get guidance => _guidance;
  CallStatus get callStatus => _callStatus;
  bool get manualOverride => _manualOverride;
  bool get isConnected => _isConnected;
  bool get classificationTimedOut => _classificationTimedOut;
  List<SubsystemError> get subsystemErrors =>
      List.unmodifiable(_subsystemErrors);
  bool get isDispatching => _isDispatching;

  /// Whether the classification has low confidence (< 0.7).
  bool get isLowConfidence =>
      _classification != null && _classification!.isLowConfidence;

  /// Whether the caller state is INCOHERENT.
  bool get isCallerIncoherent =>
      _callerState != null && _callerState!.isIncoherent;

  /// Whether the call is in a state that requires full manual handling.
  bool get requiresManualHandling =>
      _classificationTimedOut || _manualOverride;

  // ---------------------------------------------------------------------------
  // Subscription management
  // ---------------------------------------------------------------------------

  /// Subscribe to all Firebase RTDB streams for [callId].
  ///
  /// Cancels any existing subscriptions first. Starts the 8-second
  /// classification timeout timer.
  void subscribeToCall(String callId) {
    _cancelSubscriptions();

    _activeCallId = callId;
    _transcript = '';
    _classification = null;
    _callerState = null;
    _dispatchCard = null;
    _guidance = null;
    _callStatus = CallStatus.active;
    _manualOverride = false;
    _classificationTimedOut = false;
    _callStartTime = DateTime.now();
    _subsystemErrors.clear();
    _isDispatching = false;

    // Start classification timeout timer (8 seconds per Requirement 11.4).
    _startClassificationTimeout();

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

    // Subscribe to transcript stream.
    _subscriptions.add(
      _firebaseService.transcriptStream(callId).listen(
        (transcript) {
          _transcript = transcript;
          notifyListeners();
        },
        onError: (error) => _addSubsystemError(
          'Speech Ingestion',
          'Transcript stream error: $error',
        ),
      ),
    );

    // Subscribe to classification stream.
    _subscriptions.add(
      _firebaseService.classificationStream(callId).listen(
        (classification) {
          _classification = classification;
          if (classification != null) {
            _classificationTimedOut = false;
            _timeoutTimer?.cancel();
          }
          notifyListeners();
        },
        onError: (error) => _addSubsystemError(
          'Intelligence Engine',
          'Classification stream error: $error',
        ),
      ),
    );

    // Subscribe to caller state stream.
    _subscriptions.add(
      _firebaseService.callerStateStream(callId).listen(
        (callerState) {
          _callerState = callerState;
          notifyListeners();
        },
        onError: (error) => _addSubsystemError(
          'Intelligence Engine',
          'Caller state stream error: $error',
        ),
      ),
    );

    // Subscribe to dispatch card stream.
    _subscriptions.add(
      _firebaseService.dispatchCardStream(callId).listen(
        (dispatchCard) {
          _dispatchCard = dispatchCard;
          notifyListeners();
        },
        onError: (error) => _addSubsystemError(
          'Dispatch Engine',
          'Dispatch card stream error: $error',
        ),
      ),
    );

    // Subscribe to guidance stream.
    _subscriptions.add(
      _firebaseService.guidanceStream(callId).listen(
        (guidance) {
          _guidance = guidance;
          notifyListeners();
        },
        onError: (error) => _addSubsystemError(
          'Guidance Generator',
          'Guidance stream error: $error',
        ),
      ),
    );

    // Subscribe to call status.
    _subscriptions.add(
      _firebaseService.callStatusStream(callId).listen(
        (status) {
          _callStatus = status;
          notifyListeners();
        },
      ),
    );

    // Subscribe to manual override flag.
    _subscriptions.add(
      _firebaseService.manualOverrideStream(callId).listen(
        (override) {
          _manualOverride = override;
          notifyListeners();
        },
      ),
    );

    notifyListeners();
  }

  /// Cancel all active subscriptions and timers.
  void _cancelSubscriptions() {
    for (final sub in _subscriptions) {
      sub.cancel();
    }
    _subscriptions.clear();
    _timeoutTimer?.cancel();
    _timeoutTimer = null;
  }

  /// Start the 8-second classification timeout timer.
  ///
  /// If no classification arrives within 8 seconds, sets
  /// [classificationTimedOut] to true (Requirement 11.4).
  void _startClassificationTimeout() {
    _timeoutTimer?.cancel();
    _timeoutTimer = Timer(const Duration(seconds: 8), () {
      if (_classification == null && _activeCallId != null) {
        _classificationTimedOut = true;
        notifyListeners();
      }
    });
  }

  /// Record a subsystem error for operator notification (Requirement 11.6).
  void _addSubsystemError(String subsystem, String message) {
    _subsystemErrors.add(SubsystemError(
      subsystem: subsystem,
      message: message,
      occurredAt: DateTime.now(),
    ));
    notifyListeners();
  }

  /// Dismiss a subsystem error by index.
  void dismissError(int index) {
    if (index >= 0 && index < _subsystemErrors.length) {
      _subsystemErrors.removeAt(index);
      notifyListeners();
    }
  }

  /// Clear all subsystem errors.
  void clearErrors() {
    _subsystemErrors.clear();
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Operator actions
  // ---------------------------------------------------------------------------

  /// Mark dispatch as in-progress (for UI loading state).
  void setDispatching(bool dispatching) {
    _isDispatching = dispatching;
    notifyListeners();
  }

  /// Update the classification with an operator override.
  void overrideClassification(EmergencyClassification overridden) {
    _classification = overridden;
    notifyListeners();
  }

  /// Disconnect from the active call.
  void disconnectCall() {
    _cancelSubscriptions();
    _activeCallId = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _cancelSubscriptions();
    super.dispose();
  }
}
