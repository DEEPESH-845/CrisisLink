/// HTTP client for BigQuery analytics endpoints used by the Admin Dashboard.
///
/// Provides methods to fetch response time analytics, classification accuracy
/// metrics, and Vertex AI trend reports from the backend analytics API.
///
/// Requirements: 9.3, 9.4, 9.5, 9.6
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

// ---------------------------------------------------------------------------
// Data classes for analytics responses
// ---------------------------------------------------------------------------

/// Response time breakdown for a single dimension (region, time-of-day, or
/// emergency type).
class ResponseTimeEntry {
  final String dimension;
  final double avgResponseMinutes;
  final double medianResponseMinutes;
  final double p95ResponseMinutes;
  final int totalIncidents;

  const ResponseTimeEntry({
    required this.dimension,
    required this.avgResponseMinutes,
    required this.medianResponseMinutes,
    required this.p95ResponseMinutes,
    required this.totalIncidents,
  });

  factory ResponseTimeEntry.fromJson(Map<String, dynamic> json) {
    return ResponseTimeEntry(
      dimension: json['dimension'] as String? ?? '',
      avgResponseMinutes:
          (json['avg_response_minutes'] as num?)?.toDouble() ?? 0.0,
      medianResponseMinutes:
          (json['median_response_minutes'] as num?)?.toDouble() ?? 0.0,
      p95ResponseMinutes:
          (json['p95_response_minutes'] as num?)?.toDouble() ?? 0.0,
      totalIncidents: json['total_incidents'] as int? ?? 0,
    );
  }
}

/// Classification accuracy metrics including false classification rate.
///
/// Property 11: rate = overrides / total, rate ∈ [0.0, 1.0],
/// rate = 0.0 when total is zero.
class ClassificationAccuracyMetrics {
  final int totalClassifications;
  final int operatorOverrides;
  final double falseClassificationRate;

  const ClassificationAccuracyMetrics({
    required this.totalClassifications,
    required this.operatorOverrides,
    required this.falseClassificationRate,
  });

  factory ClassificationAccuracyMetrics.fromJson(Map<String, dynamic> json) {
    final total = json['total_classifications'] as int? ?? 0;
    final overrides = json['operator_overrides'] as int? ?? 0;
    return ClassificationAccuracyMetrics(
      totalClassifications: total,
      operatorOverrides: overrides,
      falseClassificationRate:
          computeFalseClassificationRate(overrides, total),
    );
  }

  /// Compute the false classification rate.
  ///
  /// Property 11: rate = overrides / total_classifications.
  /// - rate ∈ [0.0, 1.0]
  /// - rate = 0.0 when total_classifications is zero
  static double computeFalseClassificationRate(
      int overrides, int totalClassifications) {
    if (totalClassifications <= 0) return 0.0;
    final rate = overrides / totalClassifications;
    return rate.clamp(0.0, 1.0);
  }
}

/// A single Vertex AI trend report entry for predictive unit pre-positioning.
class TrendReportEntry {
  final String region;
  final String timeWindow;
  final String predictedEmergencyType;
  final double confidence;
  final int recommendedUnits;
  final String generatedAt;

  const TrendReportEntry({
    required this.region,
    required this.timeWindow,
    required this.predictedEmergencyType,
    required this.confidence,
    required this.recommendedUnits,
    required this.generatedAt,
  });

  factory TrendReportEntry.fromJson(Map<String, dynamic> json) {
    return TrendReportEntry(
      region: json['region'] as String? ?? '',
      timeWindow: json['time_window'] as String? ?? '',
      predictedEmergencyType:
          json['predicted_emergency_type'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      recommendedUnits: json['recommended_units'] as int? ?? 0,
      generatedAt: json['generated_at'] as String? ?? '',
    );
  }
}

// ---------------------------------------------------------------------------
// Analytics service
// ---------------------------------------------------------------------------

/// HTTP client for the backend analytics API (BigQuery + Vertex AI).
class AnalyticsService {
  final String baseUrl;
  final String Function() _tokenProvider;
  final http.Client _client;

  AnalyticsService({
    required this.baseUrl,
    required String Function() tokenProvider,
    http.Client? client,
  })  : _tokenProvider = tokenProvider,
        _client = client ?? http.Client();

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${_tokenProvider()}',
      };

  // ---------------------------------------------------------------------------
  // Response time analytics (Requirement 9.3)
  // ---------------------------------------------------------------------------

  /// Fetch response time analytics broken down by [breakdownType].
  ///
  /// [breakdownType] is one of: `region`, `time_of_day`, `emergency_type`.
  Future<List<ResponseTimeEntry>> fetchResponseTimes({
    required String breakdownType,
  }) async {
    try {
      final uri = Uri.parse(
          '$baseUrl/api/v1/analytics/response-times?breakdown=$breakdownType');
      final response = await _client.get(uri, headers: _headers);

      if (response.statusCode == 200) {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        final entries = body['entries'] as List<dynamic>? ?? [];
        return entries
            .map((e) =>
                ResponseTimeEntry.fromJson(e as Map<String, dynamic>))
            .toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  // ---------------------------------------------------------------------------
  // Classification accuracy (Requirements 9.4, 9.6)
  // ---------------------------------------------------------------------------

  /// Fetch classification accuracy metrics from BigQuery.
  ///
  /// Returns total classifications, operator overrides, and the computed
  /// false classification rate (Property 11).
  Future<ClassificationAccuracyMetrics> fetchClassificationAccuracy() async {
    try {
      final uri = Uri.parse(
          '$baseUrl/api/v1/analytics/classification-accuracy');
      final response = await _client.get(uri, headers: _headers);

      if (response.statusCode == 200) {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        return ClassificationAccuracyMetrics.fromJson(body);
      }
      return const ClassificationAccuracyMetrics(
        totalClassifications: 0,
        operatorOverrides: 0,
        falseClassificationRate: 0.0,
      );
    } catch (_) {
      return const ClassificationAccuracyMetrics(
        totalClassifications: 0,
        operatorOverrides: 0,
        falseClassificationRate: 0.0,
      );
    }
  }

  // ---------------------------------------------------------------------------
  // Vertex AI trend reports (Requirement 9.5)
  // ---------------------------------------------------------------------------

  /// Fetch Vertex AI trend reports for predictive unit pre-positioning.
  Future<List<TrendReportEntry>> fetchTrendReports() async {
    try {
      final uri =
          Uri.parse('$baseUrl/api/v1/analytics/trend-reports');
      final response = await _client.get(uri, headers: _headers);

      if (response.statusCode == 200) {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        final entries = body['entries'] as List<dynamic>? ?? [];
        return entries
            .map((e) =>
                TrendReportEntry.fromJson(e as Map<String, dynamic>))
            .toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  // ---------------------------------------------------------------------------
  // Override recording (Requirement 9.4)
  // ---------------------------------------------------------------------------

  /// Record an operator override as a negative label for classification
  /// accuracy monitoring.
  ///
  /// This is called from the Operator Dashboard when an override occurs,
  /// and the Admin Dashboard reads the aggregated metrics.
  Future<bool> recordOverrideLabel({
    required String callId,
    required String operatorId,
    required Map<String, dynamic> originalClassification,
    required Map<String, dynamic> overriddenClassification,
  }) async {
    try {
      final uri = Uri.parse(
          '$baseUrl/api/v1/analytics/record-override');
      final response = await _client.post(
        uri,
        headers: _headers,
        body: jsonEncode({
          'call_id': callId,
          'operator_id': operatorId,
          'original': originalClassification,
          'overridden': overriddenClassification,
          'timestamp': DateTime.now().toUtc().toIso8601String(),
        }),
      );
      return response.statusCode == 200 || response.statusCode == 201;
    } catch (_) {
      return false;
    }
  }
}
