/// Dart data models for Dispatch Card and Dispatch Recommendation.
///
/// Requirements: 4.3, 4.4, 4.6, 6.3
library;

/// A single ranked dispatch recommendation for a response unit.
class DispatchRecommendation {
  final String unitId;
  final String unitType;
  final String hospitalOrStation;
  final double etaMinutes;
  final double capabilityMatch;
  final double compositeScore;
  final double distanceKm;

  const DispatchRecommendation({
    required this.unitId,
    required this.unitType,
    required this.hospitalOrStation,
    required this.etaMinutes,
    required this.capabilityMatch,
    required this.compositeScore,
    required this.distanceKm,
  });

  factory DispatchRecommendation.fromJson(Map<String, dynamic> json) {
    return DispatchRecommendation(
      unitId: json['unit_id'] as String? ?? '',
      unitType: json['unit_type'] as String? ?? '',
      hospitalOrStation: json['hospital_or_station'] as String? ?? '',
      etaMinutes: (json['eta_minutes'] as num?)?.toDouble() ?? 0.0,
      capabilityMatch: (json['capability_match'] as num?)?.toDouble() ?? 0.0,
      compositeScore: (json['composite_score'] as num?)?.toDouble() ?? 0.0,
      distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'unit_id': unitId,
        'unit_type': unitType,
        'hospital_or_station': hospitalOrStation,
        'eta_minutes': etaMinutes,
        'capability_match': capabilityMatch,
        'composite_score': compositeScore,
        'distance_km': distanceKm,
      };
}

/// Ranked list of dispatch recommendations for a call.
class DispatchCard {
  final String callId;
  final List<DispatchRecommendation> recommendations;
  final String generatedAt;
  final String classificationRef;

  const DispatchCard({
    required this.callId,
    required this.recommendations,
    required this.generatedAt,
    required this.classificationRef,
  });

  factory DispatchCard.fromJson(Map<String, dynamic> json) {
    return DispatchCard(
      callId: json['call_id'] as String? ?? '',
      recommendations: (json['recommendations'] as List<dynamic>?)
              ?.map((e) =>
                  DispatchRecommendation.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      generatedAt: json['generated_at'] as String? ?? '',
      classificationRef: json['classification_ref'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'call_id': callId,
        'recommendations': recommendations.map((r) => r.toJson()).toList(),
        'generated_at': generatedAt,
        'classification_ref': classificationRef,
      };
}
