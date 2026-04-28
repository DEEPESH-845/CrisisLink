/// Dart data models for Call Session and Guidance state.
///
/// Requirements: 6.1, 6.2, 6.5
library;

import 'emergency_classification.dart';
import 'dispatch_card.dart';

/// Call session status.
enum CallStatus {
  active('active'),
  dispatched('dispatched'),
  resolved('resolved'),
  manualOverride('manual_override');

  const CallStatus(this.value);
  final String value;

  static CallStatus fromString(String s) =>
      CallStatus.values.firstWhere(
        (e) => e.value == s,
        orElse: () => CallStatus.active,
      );
}

/// Guidance generation status.
enum GuidanceStatus {
  generating('generating'),
  active('active'),
  completed('completed'),
  notApplicable('not_applicable');

  const GuidanceStatus(this.value);
  final String value;

  static GuidanceStatus fromString(String s) =>
      GuidanceStatus.values.firstWhere(
        (e) => e.value == s,
        orElse: () => GuidanceStatus.notApplicable,
      );
}

/// Guidance generation state for a call session.
class Guidance {
  final GuidanceStatus status;
  final String language;
  final String protocolType;

  const Guidance({
    required this.status,
    required this.language,
    required this.protocolType,
  });

  factory Guidance.fromJson(Map<String, dynamic> json) {
    return Guidance(
      status:
          GuidanceStatus.fromString(json['status'] as String? ?? 'not_applicable'),
      language: json['language'] as String? ?? '',
      protocolType: json['protocol_type'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'status': status.value,
        'language': language,
        'protocol_type': protocolType,
      };
}

/// Full call session state stored in Firebase RTDB.
class CallSession {
  final String callId;
  final CallStatus status;
  final String transcript;
  final EmergencyClassification? classification;
  final CallerState? callerState;
  final DispatchCard? dispatchCard;
  final String? confirmedUnit;
  final Guidance? guidance;
  final bool manualOverride;
  final String startedAt;
  final String updatedAt;

  const CallSession({
    required this.callId,
    required this.status,
    this.transcript = '',
    this.classification,
    this.callerState,
    this.dispatchCard,
    this.confirmedUnit,
    this.guidance,
    this.manualOverride = false,
    required this.startedAt,
    required this.updatedAt,
  });

  factory CallSession.fromJson(Map<String, dynamic> json) {
    return CallSession(
      callId: json['call_id'] as String? ?? '',
      status: CallStatus.fromString(json['status'] as String? ?? 'active'),
      transcript: json['transcript'] as String? ?? '',
      classification: json['classification'] != null
          ? EmergencyClassification.fromJson(
              json['classification'] as Map<String, dynamic>)
          : null,
      callerState: json['caller_state'] != null
          ? CallerState.fromJson(json['caller_state'] as Map<String, dynamic>)
          : null,
      dispatchCard: json['dispatch_card'] != null
          ? DispatchCard.fromJson(
              json['dispatch_card'] as Map<String, dynamic>)
          : null,
      confirmedUnit: json['confirmed_unit'] as String?,
      guidance: json['guidance'] != null
          ? Guidance.fromJson(json['guidance'] as Map<String, dynamic>)
          : null,
      manualOverride: json['manual_override'] as bool? ?? false,
      startedAt: json['started_at'] as String? ?? '',
      updatedAt: json['updated_at'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'call_id': callId,
        'status': status.value,
        'transcript': transcript,
        'classification': classification?.toJson(),
        'caller_state': callerState?.toJson(),
        'dispatch_card': dispatchCard?.toJson(),
        'confirmed_unit': confirmedUnit,
        'guidance': guidance?.toJson(),
        'manual_override': manualOverride,
        'started_at': startedAt,
        'updated_at': updatedAt,
      };
}
