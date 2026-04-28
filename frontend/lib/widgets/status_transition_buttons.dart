/// Status transition buttons for the Responder App.
///
/// Displays the current unit status and a button to transition to the
/// next valid status. Enforces the valid transition graph (Property 10):
///
///   available → dispatched → on_scene → returning → available
///
/// Only the responder-controlled transitions are shown:
///   dispatched → on_scene → returning → available
///
/// The `available → dispatched` transition is triggered by the dispatch
/// system, not by the responder.
///
/// Requirements: 7.4, 8.2
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/response_unit.dart';
import '../providers/responder_provider.dart';
import '../services/responder_firebase_service.dart';

/// Status transition button bar for the responder.
class StatusTransitionButtons extends StatelessWidget {
  const StatusTransitionButtons({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ResponderProvider>(
      builder: (context, provider, _) {
        final currentStatus = provider.unitStatus;
        final nextStatus = provider.nextValidStatus;
        final isUpdating = provider.isUpdatingStatus;
        final error = provider.statusUpdateError;

        return Card(
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                // Header
                Row(
                  children: [
                    Icon(
                      _statusIcon(currentStatus),
                      color: _statusColor(currentStatus),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Unit Status',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                  ],
                ),
                const Divider(height: 20),

                // Current status display
                _StatusBadge(status: currentStatus),
                const SizedBox(height: 16),

                // Status flow visualization
                _StatusFlow(currentStatus: currentStatus),
                const SizedBox(height: 16),

                // Transition button
                if (nextStatus != null &&
                    _isResponderTransition(currentStatus))
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: isUpdating
                          ? null
                          : () => _onTransition(context, provider),
                      icon: isUpdating
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                              ),
                            )
                          : Icon(_statusIcon(nextStatus)),
                      label: Text(
                        isUpdating
                            ? 'Updating…'
                            : _transitionLabel(currentStatus, nextStatus),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _statusColor(nextStatus),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        textStyle: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),

                // Waiting for dispatch message
                if (currentStatus == UnitStatus.available)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.hourglass_empty,
                            size: 18, color: Colors.grey.shade600),
                        const SizedBox(width: 8),
                        Text(
                          'Waiting for dispatch assignment',
                          style: TextStyle(color: Colors.grey.shade600),
                        ),
                      ],
                    ),
                  ),

                // Error message
                if (error != null) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.red.shade200),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.error_outline,
                            size: 18, color: Colors.red.shade700),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            error,
                            style: TextStyle(
                              fontSize: 13,
                              color: Colors.red.shade700,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  /// Whether the current status allows a responder-initiated transition.
  ///
  /// The `available → dispatched` transition is system-initiated (dispatch
  /// confirmation), so the responder only controls:
  /// dispatched → on_scene, on_scene → returning, returning → available.
  bool _isResponderTransition(UnitStatus status) {
    return status == UnitStatus.dispatched ||
        status == UnitStatus.onScene ||
        status == UnitStatus.returning;
  }

  Future<void> _onTransition(
    BuildContext context,
    ResponderProvider provider,
  ) async {
    final success = await provider.transitionToNext();
    if (!success && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            provider.statusUpdateError ?? 'Status update failed',
          ),
          backgroundColor: Colors.red.shade700,
        ),
      );
    }
  }

  String _transitionLabel(UnitStatus current, UnitStatus next) {
    return switch (next) {
      UnitStatus.onScene => 'Arrived On Scene',
      UnitStatus.returning => 'Returning to Station',
      UnitStatus.available => 'Mark Available',
      UnitStatus.dispatched => 'Dispatched',
    };
  }

  IconData _statusIcon(UnitStatus status) {
    return switch (status) {
      UnitStatus.available => Icons.check_circle,
      UnitStatus.dispatched => Icons.directions_car,
      UnitStatus.onScene => Icons.location_on,
      UnitStatus.returning => Icons.home,
    };
  }

  Color _statusColor(UnitStatus status) {
    return switch (status) {
      UnitStatus.available => Colors.green.shade700,
      UnitStatus.dispatched => Colors.blue.shade700,
      UnitStatus.onScene => Colors.orange.shade700,
      UnitStatus.returning => Colors.purple.shade700,
    };
  }
}

/// Colored badge showing the current status.
class _StatusBadge extends StatelessWidget {
  final UnitStatus status;

  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      UnitStatus.available => Colors.green,
      UnitStatus.dispatched => Colors.blue,
      UnitStatus.onScene => Colors.orange,
      UnitStatus.returning => Colors.purple,
    };

    final label = switch (status) {
      UnitStatus.available => 'Available',
      UnitStatus.dispatched => 'Dispatched',
      UnitStatus.onScene => 'On Scene',
      UnitStatus.returning => 'Returning',
    };

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: BoxDecoration(
        color: color.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.shade200),
      ),
      child: Center(
        child: Text(
          label,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: color.shade800,
          ),
        ),
      ),
    );
  }
}

/// Visual flow showing the status transition chain.
class _StatusFlow extends StatelessWidget {
  final UnitStatus currentStatus;

  const _StatusFlow({required this.currentStatus});

  @override
  Widget build(BuildContext context) {
    final statuses = UnitStatus.values;

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        for (int i = 0; i < statuses.length; i++) ...[
          _FlowDot(
            label: _shortLabel(statuses[i]),
            isActive: statuses[i] == currentStatus,
            isPast: statuses[i].index < currentStatus.index,
          ),
          if (i < statuses.length - 1)
            Expanded(
              child: Container(
                height: 2,
                color: statuses[i].index < currentStatus.index
                    ? Colors.green.shade400
                    : Colors.grey.shade300,
              ),
            ),
        ],
      ],
    );
  }

  String _shortLabel(UnitStatus status) {
    return switch (status) {
      UnitStatus.available => 'AVL',
      UnitStatus.dispatched => 'DSP',
      UnitStatus.onScene => 'SCN',
      UnitStatus.returning => 'RTN',
    };
  }
}

/// Single dot in the status flow visualization.
class _FlowDot extends StatelessWidget {
  final String label;
  final bool isActive;
  final bool isPast;

  const _FlowDot({
    required this.label,
    required this.isActive,
    required this.isPast,
  });

  @override
  Widget build(BuildContext context) {
    final color = isActive
        ? Colors.blue.shade700
        : isPast
            ? Colors.green.shade400
            : Colors.grey.shade400;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: isActive ? 28 : 20,
          height: isActive ? 28 : 20,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color,
            border: isActive
                ? Border.all(color: Colors.blue.shade200, width: 3)
                : null,
          ),
          child: isActive
              ? const Icon(Icons.circle, size: 10, color: Colors.white)
              : null,
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
            color: color,
          ),
        ),
      ],
    );
  }
}
