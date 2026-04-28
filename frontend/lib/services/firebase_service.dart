/// Firebase Realtime Database stream subscription service.
///
/// Provides real-time listeners for all call-level paths used by the
/// Operator Dashboard. Uses `onValue` streams for sub-200ms state propagation.
///
/// Requirements: 6.1, 6.2, 11.2, 11.6
library;

import 'dart:async';

import 'package:firebase_database/firebase_database.dart';

import '../models/call_session.dart';
import '../models/dispatch_card.dart';
import '../models/emergency_classification.dart';

/// Service that manages Firebase RTDB stream subscriptions for a single call.
class FirebaseService {
  final FirebaseDatabase _database;

  FirebaseService({FirebaseDatabase? database})
      : _database = database ?? FirebaseDatabase.instance;

  // ---------------------------------------------------------------------------
  // Connection state
  // ---------------------------------------------------------------------------

  /// Stream that emits `true` when connected to Firebase RTDB, `false` on
  /// disconnect. Used by [ConnectionBanner] to show reconnecting state.
  Stream<bool> get connectionState {
    return _database
        .ref('.info/connected')
        .onValue
        .map((event) => event.snapshot.value as bool? ?? false);
  }

  // ---------------------------------------------------------------------------
  // Call-level streams
  // ---------------------------------------------------------------------------

  /// Live rolling transcript for [callId].
  Stream<String> transcriptStream(String callId) {
    return _database
        .ref('calls/$callId/transcript')
        .onValue
        .map((event) => event.snapshot.value as String? ?? '');
  }

  /// Streaming Emergency Classification for [callId].
  /// Emits partial updates as the Intelligence Engine writes token-by-token.
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

  /// Caller state updates for [callId].
  Stream<CallerState?> callerStateStream(String callId) {
    return _database
        .ref('calls/$callId/caller_state')
        .onValue
        .map((event) {
      final data = event.snapshot.value;
      if (data == null) return null;
      return CallerState.fromJson(Map<String, dynamic>.from(data as Map));
    });
  }

  /// Dispatch card (ranked recommendations) for [callId].
  Stream<DispatchCard?> dispatchCardStream(String callId) {
    return _database
        .ref('calls/$callId/dispatch_card')
        .onValue
        .map((event) {
      final data = event.snapshot.value;
      if (data == null) return null;
      return DispatchCard.fromJson(Map<String, dynamic>.from(data as Map));
    });
  }

  /// Guidance status for [callId].
  Stream<Guidance?> guidanceStream(String callId) {
    return _database
        .ref('calls/$callId/guidance')
        .onValue
        .map((event) {
      final data = event.snapshot.value;
      if (data == null) return null;
      return Guidance.fromJson(Map<String, dynamic>.from(data as Map));
    });
  }

  /// Call status for [callId].
  Stream<CallStatus> callStatusStream(String callId) {
    return _database
        .ref('calls/$callId/status')
        .onValue
        .map((event) {
      final value = event.snapshot.value as String?;
      return CallStatus.fromString(value ?? 'active');
    });
  }

  /// Manual override flag for [callId].
  Stream<bool> manualOverrideStream(String callId) {
    return _database
        .ref('calls/$callId/manual_override')
        .onValue
        .map((event) => event.snapshot.value as bool? ?? false);
  }

  // ---------------------------------------------------------------------------
  // Write operations
  // ---------------------------------------------------------------------------

  /// Write dispatch confirmation for [callId] with the selected [unitId].
  Future<void> confirmDispatch(String callId, String unitId) async {
    await _database.ref('calls/$callId').update({
      'confirmed_unit': unitId,
      'status': CallStatus.dispatched.value,
      'updated_at': DateTime.now().toUtc().toIso8601String(),
    });
  }

  /// Set manual override flag for [callId].
  Future<void> setManualOverride(String callId, {bool override = true}) async {
    await _database.ref('calls/$callId').update({
      'manual_override': override,
      'status': override
          ? CallStatus.manualOverride.value
          : CallStatus.active.value,
      'updated_at': DateTime.now().toUtc().toIso8601String(),
    });
  }

  /// Write a classification override to the call session.
  Future<void> writeClassificationOverride(
    String callId,
    EmergencyClassification overriddenClassification,
  ) async {
    await _database.ref('calls/$callId/classification').set(
          overriddenClassification.toJson(),
        );
    await _database.ref('calls/$callId').update({
      'updated_at': DateTime.now().toUtc().toIso8601String(),
    });
  }
}
