/// Audit logging service for operator overrides.
///
/// Writes audit log entries to BigQuery via the backend audit endpoint.
/// Used when operators override AI classifications.
///
/// Requirements: 6.7, 10.4
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

/// Types of audit events the operator dashboard can produce.
enum OperatorAuditEventType {
  operatorOverride('operator_override'),
  dispatch('dispatch'),
  manualTakeover('manual_takeover');

  const OperatorAuditEventType(this.value);
  final String value;
}

/// Service that writes operator actions to the BigQuery audit log via backend.
class AuditService {
  final String baseUrl;
  final String Function() _tokenProvider;
  final http.Client _client;

  AuditService({
    required this.baseUrl,
    required String Function() tokenProvider,
    http.Client? client,
  })  : _tokenProvider = tokenProvider,
        _client = client ?? http.Client();

  /// Log an operator override event.
  ///
  /// [callId] — the active call session.
  /// [operatorId] — the authenticated operator's ID.
  /// [eventType] — the type of operator action.
  /// [payload] — event-specific data (e.g., original and overridden values).
  Future<bool> logEvent({
    required String callId,
    required String operatorId,
    required OperatorAuditEventType eventType,
    required Map<String, dynamic> payload,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/audit/log');
      final response = await _client.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${_tokenProvider()}',
        },
        body: jsonEncode({
          'call_id': callId,
          'event_type': eventType.value,
          'payload': payload,
          'actor': operatorId,
          'timestamp': DateTime.now().toUtc().toIso8601String(),
        }),
      );

      return response.statusCode == 200 || response.statusCode == 201;
    } catch (_) {
      // Audit logging failures should not block operator workflow.
      // The error is silently swallowed; a production system would use
      // a local queue with retry.
      return false;
    }
  }

  /// Log a classification override specifically.
  Future<bool> logClassificationOverride({
    required String callId,
    required String operatorId,
    required Map<String, dynamic> originalClassification,
    required Map<String, dynamic> overriddenClassification,
  }) async {
    return logEvent(
      callId: callId,
      operatorId: operatorId,
      eventType: OperatorAuditEventType.operatorOverride,
      payload: {
        'original': originalClassification,
        'overridden': overriddenClassification,
      },
    );
  }
}
