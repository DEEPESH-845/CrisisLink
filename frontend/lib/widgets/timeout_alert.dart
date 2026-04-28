/// Classification timeout alert widget.
///
/// Displays a prominent alert when the Intelligence Engine fails to produce
/// a classification within 8 seconds. Presents the call for full manual
/// handling on timeout.
///
/// Requirements: 11.4
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/call_provider.dart';
import '../services/firebase_service.dart';

/// Alert displayed when classification times out after 8 seconds.
///
/// Offers the operator a button to take manual control of the call.
class TimeoutAlert extends StatelessWidget {
  const TimeoutAlert({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<CallProvider>(
      builder: (context, provider, _) {
        if (!provider.classificationTimedOut) {
          return const SizedBox.shrink();
        }

        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.red.shade50,
            border: Border.all(color: Colors.red.shade600, width: 2),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Icon(Icons.timer_off, color: Colors.red.shade700, size: 28),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Classification Timeout',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: Colors.red.shade900,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'AI classification not received within 8 seconds. '
                          'This call requires full manual handling.',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.red.shade800,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () => _takeManualControl(context, provider),
                  icon: const Icon(Icons.pan_tool),
                  label: const Text('Take Manual Control'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red.shade700,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _takeManualControl(
    BuildContext context,
    CallProvider provider,
  ) async {
    final callId = provider.activeCallId;
    if (callId == null) return;

    final firebaseService = context.read<FirebaseService>();
    await firebaseService.setManualOverride(callId);
  }
}
