/// Subsystem error notification widget.
///
/// Notifies the operator when any subsystem encounters an unrecoverable
/// error, preserving manual call-handling capability. Each error is
/// dismissible.
///
/// Requirements: 11.6
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/call_provider.dart';

/// Displays a stack of subsystem error notifications.
///
/// Each notification identifies the failing subsystem and provides a
/// dismiss action. The operator retains full manual call-handling
/// capability regardless of subsystem failures.
class ErrorNotification extends StatelessWidget {
  const ErrorNotification({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<CallProvider>(
      builder: (context, provider, _) {
        final errors = provider.subsystemErrors;

        if (errors.isEmpty) {
          return const SizedBox.shrink();
        }

        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header with clear-all button
            if (errors.length > 1)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton.icon(
                      onPressed: provider.clearErrors,
                      icon: const Icon(Icons.clear_all, size: 16),
                      label: const Text('Clear all',
                          style: TextStyle(fontSize: 12)),
                      style: TextButton.styleFrom(
                        foregroundColor: Colors.red.shade700,
                        visualDensity: VisualDensity.compact,
                      ),
                    ),
                  ],
                ),
              ),

            // Error cards
            ...errors.asMap().entries.map(
                  (entry) => _ErrorCard(
                    error: entry.value,
                    onDismiss: () => provider.dismissError(entry.key),
                  ),
                ),
          ],
        );
      },
    );
  }
}

/// A single dismissible error notification card.
class _ErrorCard extends StatelessWidget {
  final SubsystemError error;
  final VoidCallback onDismiss;

  const _ErrorCard({
    required this.error,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        border: Border.all(color: Colors.red.shade300),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error, color: Colors.red.shade700, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${error.subsystem} Error',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: Colors.red.shade900,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  error.message,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.red.shade800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Manual call handling is available.',
                  style: TextStyle(
                    fontSize: 11,
                    fontStyle: FontStyle.italic,
                    color: Colors.red.shade600,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: onDismiss,
            icon: Icon(Icons.close, size: 16, color: Colors.red.shade400),
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
            tooltip: 'Dismiss',
          ),
        ],
      ),
    );
  }
}
