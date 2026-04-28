/// Dart data models mirroring the backend Emergency Classification Pydantic models.
///
/// Requirements: 2.1, 2.2, 2.3, 2.5, 3.1, 3.2
library;

/// Emergency classification type.
enum EmergencyType {
  medical('MEDICAL'),
  fire('FIRE'),
  crime('CRIME'),
  accident('ACCIDENT'),
  disaster('DISASTER'),
  unknown('UNKNOWN');

  const EmergencyType(this.value);
  final String value;

  static EmergencyType fromString(String s) =>
      EmergencyType.values.firstWhere(
        (e) => e.value == s,
        orElse: () => EmergencyType.unknown,
      );
}

/// Emergency severity level.
enum Severity {
  critical('CRITICAL'),
  high('HIGH'),
  moderate('MODERATE'),
  low('LOW');

  const Severity(this.value);
  final String value;

  static Severity fromString(String s) =>
      Severity.values.firstWhere(
        (e) => e.value == s,
        orElse: () => Severity.low,
      );
}

/// Caller panic level classification.
enum PanicLevel {
  panicHigh('PANIC_HIGH'),
  panicMed('PANIC_MED'),
  calm('CALM'),
  incoherent('INCOHERENT');

  const PanicLevel(this.value);
  final String value;

  static PanicLevel fromString(String s) =>
      PanicLevel.values.firstWhere(
        (e) => e.value == s,
        orElse: () => PanicLevel.calm,
      );
}

/// Caller role classification.
enum CallerRole {
  victim('VICTIM'),
  bystander('BYSTANDER'),
  witness('WITNESS');

  const CallerRole(this.value);
  final String value;

  static CallerRole fromString(String s) =>
      CallerRole.values.firstWhere(
        (e) => e.value == s,
        orElse: () => CallerRole.witness,
      );
}

/// Caller emotional and cognitive state.
class CallerState {
  final PanicLevel panicLevel;
  final CallerRole callerRole;

  const CallerState({
    required this.panicLevel,
    required this.callerRole,
  });

  factory CallerState.fromJson(Map<String, dynamic> json) {
    return CallerState(
      panicLevel: PanicLevel.fromString(json['panic_level'] as String? ?? 'CALM'),
      callerRole: CallerRole.fromString(json['caller_role'] as String? ?? 'WITNESS'),
    );
  }

  Map<String, dynamic> toJson() => {
        'panic_level': panicLevel.value,
        'caller_role': callerRole.value,
      };

  bool get isIncoherent => panicLevel == PanicLevel.incoherent;
}

/// Structured output from the Intelligence Engine for emergency triage.
class EmergencyClassification {
  final String callId;
  final EmergencyType emergencyType;
  final Severity severity;
  final CallerState callerState;
  final String languageDetected;
  final List<String> keyFacts;
  final double confidence;
  final String timestamp;
  final String modelVersion;

  const EmergencyClassification({
    required this.callId,
    required this.emergencyType,
    required this.severity,
    required this.callerState,
    required this.languageDetected,
    required this.keyFacts,
    required this.confidence,
    required this.timestamp,
    required this.modelVersion,
  });

  factory EmergencyClassification.fromJson(Map<String, dynamic> json) {
    return EmergencyClassification(
      callId: json['call_id'] as String? ?? '',
      emergencyType:
          EmergencyType.fromString(json['emergency_type'] as String? ?? 'UNKNOWN'),
      severity: Severity.fromString(json['severity'] as String? ?? 'LOW'),
      callerState: json['caller_state'] != null
          ? CallerState.fromJson(json['caller_state'] as Map<String, dynamic>)
          : const CallerState(
              panicLevel: PanicLevel.calm,
              callerRole: CallerRole.witness,
            ),
      languageDetected: json['language_detected'] as String? ?? 'en',
      keyFacts: (json['key_facts'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      timestamp: json['timestamp'] as String? ?? '',
      modelVersion: json['model_version'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'call_id': callId,
        'emergency_type': emergencyType.value,
        'severity': severity.value,
        'caller_state': callerState.toJson(),
        'language_detected': languageDetected,
        'key_facts': keyFacts,
        'confidence': confidence,
        'timestamp': timestamp,
        'model_version': modelVersion,
      };

  /// Whether this classification has low confidence (< 0.7) requiring manual review.
  bool get isLowConfidence => confidence < 0.7;
}
