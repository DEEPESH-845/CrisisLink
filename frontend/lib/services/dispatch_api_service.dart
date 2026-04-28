/// HTTP client for the Dispatch Service confirm endpoint.
///
/// Requirements: 4.5, 6.3, 6.4
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

/// Result of a dispatch confirmation request.
class DispatchConfirmResult {
  final bool success;
  final String unitId;
  final String? errorMessage;

  const DispatchConfirmResult({
    required this.success,
    required this.unitId,
    this.errorMessage,
  });
}

/// Service that communicates with the Dispatch Service backend.
class DispatchApiService {
  final String baseUrl;
  final String Function() _tokenProvider;
  final http.Client _client;

  DispatchApiService({
    required this.baseUrl,
    required String Function() tokenProvider,
    http.Client? client,
  })  : _tokenProvider = tokenProvider,
        _client = client ?? http.Client();

  /// Confirm dispatch of [unitId] for [callId].
  ///
  /// Calls `POST /api/v1/calls/{call_id}/dispatch/confirm` with Bearer auth.
  Future<DispatchConfirmResult> confirmDispatch({
    required String callId,
    required String unitId,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/calls/$callId/dispatch/confirm');
      final response = await _client.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${_tokenProvider()}',
        },
        body: jsonEncode({'unit_id': unitId}),
      );

      if (response.statusCode == 200) {
        return DispatchConfirmResult(success: true, unitId: unitId);
      } else {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        return DispatchConfirmResult(
          success: false,
          unitId: unitId,
          errorMessage: body['detail'] as String? ?? 'Dispatch confirmation failed',
        );
      }
    } catch (e) {
      return DispatchConfirmResult(
        success: false,
        unitId: unitId,
        errorMessage: 'Network error: $e',
      );
    }
  }
}
