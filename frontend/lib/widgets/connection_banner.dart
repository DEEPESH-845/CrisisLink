/// Reconnecting banner for Firebase RTDB connection loss.
///
/// Displays a banner at the top of the dashboard when the Firebase RTDB
/// WebSocket connection is lost. Auto-reconnect is handled by the Firebase
/// SDK; this widget provides visual feedback to the operator.
///
/// Requirements: 11.6
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/call_provider.dart';

/// Banner shown when Firebase RTDB connection is lost.
class ConnectionBanner extends StatelessWidget {
  const ConnectionBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<CallProvider>(
      builder: (context, provider, _) {
        if (provider.isConnected) {
          return const SizedBox.shrink();
        }

        return Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          color: Colors.orange.shade700,
          child: Row(
            children: [
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Connection lost — reconnecting to Firebase. '
                  'Data may be stale.',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w500,
                    fontSize: 13,
                  ),
                ),
              ),
              Icon(
                Icons.cloud_off,
                color: Colors.white.withOpacity(0.8),
                size: 20,
              ),
            ],
          ),
        );
      },
    );
  }
}
