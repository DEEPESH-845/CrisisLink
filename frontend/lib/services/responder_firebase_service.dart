/// Firebase Realtime Database service for the Responder App.
///
/// Provides real-time listeners for unit dispatch and call classification,
/// plus write operations for status updates and GPS location pushes.
///
/// Firebase RTDB paths:
/// - `/units/{unit_id}/dispatch` — incoming dispatch details
/// - `/calls/{call_id}/classification` — case context
/// - `/units/{unit_id}/status` — unit operational status
/// - `/units/{unit_id}/location` — GPS coordinates
///
/// Requirements: 7.1, 7.3, 7.4, 7.5, 8.1, 8.2
library;

import 'dart:async';

import 'package:firebase_database/firebase_database.dart';

import '../models/emergency_classification.dart';
import '../models/response_unit.dart';

/// Dispatch details pushed to a responder unit via Firebase RTDB.
class DispatchDetails {
  final String callId;
  final String emergencyType;
  final String severity;
  final double callerLat;
  final double callerLng;
  final String? callerStateSummary;
  final List<String> keyFacts;
  final String dispatchedAt;

  const DispatchDetails({
    required this.callId,
    required this.emergencyType,
    required this.severity,
    required this.callerLat,
    required this.callerLng,
    this.callerStateSummary,
    this.keyFacts = const [],
    required this.dispatchedAt,
  });

  factory DispatchDetails.fromJson(Map<String, dynamic> json) {
    return DispatchDetails(
      callId: json['call_id'] as String? ?? '',
      emergencyType: json['emergency_type'] as String? ?? 'UNKNOWN',
      severity: json['severity'] as String? ?? 'LOW',
      callerLat: (json['caller_lat'] as num?)?.toDouble() ?? 0.0,
      callerLng: (json['caller_lng'] as num?)?.toDouble() ?? 0.0,
      callerStateSummary: json['caller_state_summary'] as String?,
      keyFacts: (json['key_facts'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      dispatchedAt: json['dispatched_at'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'call_id': callId,
        'emergency_type': emergencyType,
        'severity': severity,
        'caller_lat': callerLat,
        'caller_lng': callerLng,
        'caller_state_summary': callerStateSummary,
        'key_facts': keyFacts,
        'dispatched_at': dispatchedAt,
      };
}

/// Valid status transitions for a Response Unit (Property 10).
///
/// available → dispatched → on_scene → returning → available
const Map<UnitStatus, UnitStatus> validStatusTransitions = {
  UnitStatus.available: UnitStatus.dispatched,
  UnitStatus.dispatched: UnitStatus.onScene,
  UnitStatus.onScene: UnitStatus.returning,
  UnitStatus.returning: UnitStatus.available,
};

/// Returns `true` if transitioning from [current] to [next] is valid.
bool isValidStatusTransition(UnitStatus current, UnitStatus next) {
  return validStatusTransitions[current] == next;
}

/// Firebase RTDB service for the Responder App.
///
/// Manages subscriptions to dispatch and classification data, and provides
/// write operations for status and GPS location updates.
class ResponderFirebaseService {
  final FirebaseDatabase _database;

  ResponderFirebaseService({FirebaseDatabase? database})
      : _database = database ?? FirebaseDatabase.instance;

  // ---------------------------------------------------------------------------
  // Connection state
  // ---------------------------------------------------------------------------

  /// Stream that emits `true` when connected to Firebase RTDB.
  Stream<bool> get connectionState {
    return _database
        .ref('.info/connected')
        .onValue
        .map((event) => event.snapshot.value as bool? ?? false);
  }

  // ---------------------------------------------------------------------------
  // Unit dispatch stream
  // ---------------------------------------------------------------------------

  /// Stream of dispatch details for [unitId].
  ///
  /// Listens to `/units/{unit_id}/dispatch` for incoming dispatch assignments.
  Stream<DispatchDetails?> dispatchStream(String unitId) {
    return _database
        .ref('units/$unitId/dispatch')
        .onValue
        .map((event) {
      final data = event.snapshot.value;
      if (data == null) return null;
      return DispatchDetails.fromJson(
          Map<String, dynamic>.from(data as Map));
    });
  }

  /// Stream of the unit's current status from `/units/{unit_id}/status`.
  Stream<UnitStatus> unitStatusStream(String unitId) {
    return _database
        .ref('units/$unitId/status')
        .onValue
        .map((event) {
      final value = event.snapshot.value as String?;
      return UnitStatus.fromString(value ?? 'available');
    });
  }

  // ---------------------------------------------------------------------------
  // Call classification stream (case context)
  // ---------------------------------------------------------------------------

  /// Stream of Emergency Classification for [callId] — provides case context.
  Stream<EmergencyClassification?> classificationStream(String callId) {
    return _database
        .ref('calls/$callId/classification')
        .onValue
        .map((event) {
      final data = event.snapshot.value;
      if (data == null) return null;
      return EmergencyClassification.fromJson(
          Map<String, dynamic>.from(data as Map));
    });
  }

  // ---------------------------------------------------------------------------
  // Write operations
  // ---------------------------------------------------------------------------

  /// Update the unit's status in Firebase RTDB.
  ///
  /// Validates the transition against [validStatusTransitions] before writing.
  /// Returns `true` if the write succeeded, `false` if the transition is
  /// invalid.
  ///
  /// Writes to `/units/{unit_id}/status` and updates `last_updated`.
  /// Target: < 200ms propagation (Requirement 7.5).
  Future<bool> updateUnitStatus({
    required String unitId,
    required UnitStatus currentStatus,
    required UnitStatus newStatus,
  }) async {
    if (!isValidStatusTransition(currentStatus, newStatus)) {
      return false;
    }

    await _database.ref('units/$unitId').update({
      'status': newStatus.value,
      'last_updated': ServerValue.timestamp,
    });
    return true;
  }

  /// Push GPS location to Firebase RTDB.
  ///
  /// Writes to `/units/{unit_id}/location` with lat/lng and updates
  /// `last_updated` timestamp.
  ///
  /// Called every 10 seconds by the GPS background service (Requirement 8.1).
  Future<void> pushGpsLocation({
    required String unitId,
    required double lat,
    required double lng,
  }) async {
    await _database.ref('units/$unitId').update({
      'location': {'lat': lat, 'lng': lng},
      'last_updated': ServerValue.timestamp,
    });
  }

  /// Clear the dispatch assignment for [unitId] after the responder
  /// transitions back to available.
  Future<void> clearDispatch(String unitId) async {
    await _database.ref('units/$unitId/dispatch').remove();
  }
}
