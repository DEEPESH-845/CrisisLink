/// GPS background tracking service for the Responder App.
///
/// Pushes the responder's GPS location to Firebase RTDB every 10 seconds.
/// Detects when the GPS background service stops (no update for > 30s)
/// and alerts the responder to re-enable location services.
///
/// Firebase RTDB path: `/units/{unit_id}/location`
///
/// Requirements: 7.5, 7.6, 8.1, 8.2
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import 'responder_firebase_service.dart';

/// Callback signature for obtaining the current GPS position.
///
/// In production, this wraps `Geolocator.getCurrentPosition()` or similar.
/// Accepting a callback allows unit testing without a real GPS sensor.
typedef GpsPositionProvider = Future<GpsPosition> Function();

/// A simple GPS coordinate pair.
class GpsPosition {
  final double latitude;
  final double longitude;

  const GpsPosition({required this.latitude, required this.longitude});
}

/// Status of the GPS tracking service.
enum GpsTrackingStatus {
  /// Service is running and pushing location updates.
  active,

  /// Service is stopped or paused.
  stopped,

  /// Location data is stale (no update for > 30 seconds).
  stale,

  /// GPS/location permission denied or unavailable.
  permissionDenied,
}

/// Background GPS tracking service.
///
/// Periodically fetches the device's GPS position and pushes it to
/// Firebase RTDB via [ResponderFirebaseService.pushGpsLocation].
///
/// Monitors for staleness: if no successful push occurs within 30 seconds,
/// the status transitions to [GpsTrackingStatus.stale] so the UI can
/// alert the responder to re-enable location.
class GpsService extends ChangeNotifier {
  final ResponderFirebaseService _firebaseService;
  final GpsPositionProvider _positionProvider;

  /// How often to push GPS updates (default: 10 seconds per Requirement 8.1).
  final Duration updateInterval;

  /// How long without an update before marking location as stale (30s).
  final Duration staleThreshold;

  GpsService({
    required ResponderFirebaseService firebaseService,
    required GpsPositionProvider positionProvider,
    this.updateInterval = const Duration(seconds: 10),
    this.staleThreshold = const Duration(seconds: 30),
  })  : _firebaseService = firebaseService,
        _positionProvider = positionProvider;

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  Timer? _updateTimer;
  Timer? _staleTimer;
  String? _unitId;
  GpsTrackingStatus _status = GpsTrackingStatus.stopped;
  DateTime? _lastSuccessfulPush;
  GpsPosition? _lastPosition;

  GpsTrackingStatus get status => _status;
  DateTime? get lastSuccessfulPush => _lastSuccessfulPush;
  GpsPosition? get lastPosition => _lastPosition;
  bool get isTracking => _status == GpsTrackingStatus.active;

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------

  /// Start the GPS background tracking loop for [unitId].
  ///
  /// Immediately pushes the first location, then repeats every
  /// [updateInterval].
  void startTracking(String unitId) {
    _unitId = unitId;
    _status = GpsTrackingStatus.active;
    notifyListeners();

    // Push immediately, then start periodic timer.
    _pushLocation();

    _updateTimer?.cancel();
    _updateTimer = Timer.periodic(updateInterval, (_) => _pushLocation());

    // Start stale detection timer.
    _resetStaleTimer();
  }

  /// Stop the GPS background tracking loop.
  void stopTracking() {
    _updateTimer?.cancel();
    _updateTimer = null;
    _staleTimer?.cancel();
    _staleTimer = null;
    _status = GpsTrackingStatus.stopped;
    notifyListeners();
  }

  /// Push the current GPS position to Firebase RTDB.
  Future<void> _pushLocation() async {
    if (_unitId == null) return;

    try {
      final position = await _positionProvider();
      await _firebaseService.pushGpsLocation(
        unitId: _unitId!,
        lat: position.latitude,
        lng: position.longitude,
      );

      _lastPosition = position;
      _lastSuccessfulPush = DateTime.now();

      if (_status == GpsTrackingStatus.stale) {
        _status = GpsTrackingStatus.active;
      }

      _resetStaleTimer();
      notifyListeners();
    } catch (e) {
      debugPrint('GPS push failed: $e');
      // Don't change status on transient errors — the stale timer will
      // catch persistent failures.
    }
  }

  /// Reset the stale detection timer.
  ///
  /// If no successful push occurs within [staleThreshold], mark the
  /// location as stale so the UI can alert the responder.
  void _resetStaleTimer() {
    _staleTimer?.cancel();
    _staleTimer = Timer(staleThreshold, () {
      if (_status == GpsTrackingStatus.active) {
        _status = GpsTrackingStatus.stale;
        notifyListeners();
      }
    });
  }

  /// Mark the service as having a permission issue.
  void markPermissionDenied() {
    stopTracking();
    _status = GpsTrackingStatus.permissionDenied;
    notifyListeners();
  }

  @override
  void dispose() {
    stopTracking();
    super.dispose();
  }
}
