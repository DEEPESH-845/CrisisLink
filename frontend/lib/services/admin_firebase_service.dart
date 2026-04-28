/// Firebase Realtime Database service for the Admin Dashboard.
///
/// Provides real-time listeners for live unit status and active incident data
/// used by the Admin Dashboard heatmap and unit availability overview.
///
/// Firebase RTDB paths:
/// - `/units/` — all Response_Units with status, location, capabilities
/// - `/calls/` — active and recent call sessions with classification data
///
/// Requirements: 9.1, 9.2
library;

import 'dart:async';

import 'package:firebase_database/firebase_database.dart';

import '../models/call_session.dart';
import '../models/emergency_classification.dart';
import '../models/response_unit.dart';

/// Lightweight incident summary for heatmap display.
class IncidentSummary {
  final String callId;
  final double lat;
  final double lng;
  final EmergencyType emergencyType;
  final Severity severity;
  final CallStatus status;
  final String startedAt;

  const IncidentSummary({
    required this.callId,
    required this.lat,
    required this.lng,
    required this.emergencyType,
    required this.severity,
    required this.status,
    required this.startedAt,
  });

  /// Whether this incident is currently active (not yet resolved).
  bool get isActive =>
      status == CallStatus.active || status == CallStatus.dispatched;
}

/// Firebase RTDB service for the Admin Dashboard.
///
/// Streams live unit data and incident data for the admin analytics views.
class AdminFirebaseService {
  final FirebaseDatabase _database;

  AdminFirebaseService({FirebaseDatabase? database})
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
  // Unit streams
  // ---------------------------------------------------------------------------

  /// Stream of all Response_Units from `/units/`.
  ///
  /// Emits the full list whenever any unit's data changes. Used by the
  /// unit availability overview widget.
  Stream<List<ResponseUnit>> allUnitsStream() {
    return _database.ref('units').onValue.map((event) {
      final data = event.snapshot.value;
      if (data == null) return <ResponseUnit>[];
      final map = Map<String, dynamic>.from(data as Map);
      return map.entries.map((entry) {
        final unitData = Map<String, dynamic>.from(entry.value as Map);
        // Ensure unit_id is populated from the key if missing.
        unitData['unit_id'] ??= entry.key;
        return ResponseUnit.fromJson(unitData);
      }).toList();
    });
  }

  // ---------------------------------------------------------------------------
  // Incident streams
  // ---------------------------------------------------------------------------

  /// Stream of all active and recent incidents from `/calls/`.
  ///
  /// Extracts location from classification key_facts or caller location
  /// metadata. Used by the incident heatmap widget.
  Stream<List<IncidentSummary>> incidentsStream() {
    return _database.ref('calls').onValue.map((event) {
      final data = event.snapshot.value;
      if (data == null) return <IncidentSummary>[];
      final map = Map<String, dynamic>.from(data as Map);
      final incidents = <IncidentSummary>[];

      for (final entry in map.entries) {
        final callData = Map<String, dynamic>.from(entry.value as Map);
        final callId = entry.key;

        // Extract classification data if available.
        EmergencyType emergencyType = EmergencyType.unknown;
        Severity severity = Severity.low;
        if (callData['classification'] != null) {
          final classJson =
              Map<String, dynamic>.from(callData['classification'] as Map);
          emergencyType = EmergencyType.fromString(
              classJson['emergency_type'] as String? ?? 'UNKNOWN');
          severity =
              Severity.fromString(classJson['severity'] as String? ?? 'LOW');
        }

        // Extract location from caller_location metadata if available.
        double lat = 0.0;
        double lng = 0.0;
        if (callData['caller_location'] != null) {
          final locData =
              Map<String, dynamic>.from(callData['caller_location'] as Map);
          lat = (locData['lat'] as num?)?.toDouble() ?? 0.0;
          lng = (locData['lng'] as num?)?.toDouble() ?? 0.0;
        }

        final status =
            CallStatus.fromString(callData['status'] as String? ?? 'active');
        final startedAt = callData['started_at'] as String? ?? '';

        incidents.add(IncidentSummary(
          callId: callId,
          lat: lat,
          lng: lng,
          emergencyType: emergencyType,
          severity: severity,
          status: status,
          startedAt: startedAt,
        ));
      }

      return incidents;
    });
  }
}
