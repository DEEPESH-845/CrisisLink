/// Dispatch Card widget with ranked units and one-tap dispatch confirmation.
///
/// Displays ranked Response_Unit list with unit identifier, unit type,
/// hospital/station, ETA in minutes, and capability match indicator.
/// Provides single-tap dispatch confirmation for each entry.
///
/// Requirements: 6.3, 6.4, 4.5, 4.6
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/dispatch_card.dart';
import '../providers/call_provider.dart';
import '../services/dispatch_api_service.dart';
import '../services/firebase_service.dart';

/// Dispatch Card displaying ranked response units with one-tap confirm.
class DispatchCardWidget extends StatelessWidget {
  final DispatchApiService dispatchApiService;

  const DispatchCardWidget({
    super.key,
    required this.dispatchApiService,
  });

  @override
  Widget build(BuildContext context) {
    return Consumer<CallProvider>(
      builder: (context, provider, _) {
        final dispatchCard = provider.dispatchCard;

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
                      Icons.local_shipping,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Dispatch Recommendations',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                  ],
                ),
                const Divider(height: 24),

                if (dispatchCard == null)
                  const _WaitingForDispatch()
                else if (dispatchCard.recommendations.isEmpty)
                  const _NoUnitsAvailable()
                else
                  ...dispatchCard.recommendations.asMap().entries.map(
                        (entry) => _RecommendationTile(
                          rank: entry.key + 1,
                          recommendation: entry.value,
                          callId: provider.activeCallId ?? '',
                          isDispatching: provider.isDispatching,
                          dispatchApiService: dispatchApiService,
                        ),
                      ),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// A single dispatch recommendation tile with one-tap confirm button.
class _RecommendationTile extends StatelessWidget {
  final int rank;
  final DispatchRecommendation recommendation;
  final String callId;
  final bool isDispatching;
  final DispatchApiService dispatchApiService;

  const _RecommendationTile({
    required this.rank,
    required this.recommendation,
    required this.callId,
    required this.isDispatching,
    required this.dispatchApiService,
  });

  @override
  Widget build(BuildContext context) {
    final matchPercent =
        (recommendation.capabilityMatch * 100).toStringAsFixed(0);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey.shade300),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            // Rank badge
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: rank == 1
                    ? Theme.of(context).colorScheme.primary
                    : Colors.grey.shade400,
                shape: BoxShape.circle,
              ),
              child: Center(
                child: Text(
                  '#$rank',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),

            // Unit details
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(_unitTypeIcon(recommendation.unitType),
                          size: 16, color: Colors.grey.shade700),
                      const SizedBox(width: 4),
                      Text(
                        recommendation.unitId,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _unitTypeLabel(recommendation.unitType),
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    recommendation.hospitalOrStation,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      _MetricChip(
                        icon: Icons.timer,
                        label:
                            '${recommendation.etaMinutes.toStringAsFixed(0)} min',
                      ),
                      const SizedBox(width: 8),
                      _MetricChip(
                        icon: Icons.check_circle_outline,
                        label: '$matchPercent% match',
                        color: recommendation.capabilityMatch >= 0.8
                            ? Colors.green
                            : Colors.orange,
                      ),
                      const SizedBox(width: 8),
                      _MetricChip(
                        icon: Icons.straighten,
                        label:
                            '${recommendation.distanceKm.toStringAsFixed(1)} km',
                      ),
                    ],
                  ),
                ],
              ),
            ),

            // One-tap dispatch confirm button (Requirement 4.5, 6.3)
            SizedBox(
              width: 100,
              child: ElevatedButton(
                onPressed: isDispatching
                    ? null
                    : () => _confirmDispatch(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Theme.of(context).colorScheme.primary,
                  foregroundColor: Colors.white,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
                child: isDispatching
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text('Dispatch', style: TextStyle(fontSize: 13)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Confirm dispatch: call backend, then update Firebase RTDB.
  Future<void> _confirmDispatch(BuildContext context) async {
    final provider = context.read<CallProvider>();
    final firebaseService = context.read<FirebaseService>();

    provider.setDispatching(true);

    // Call Dispatch Service confirm endpoint (Requirement 4.5).
    final result = await dispatchApiService.confirmDispatch(
      callId: callId,
      unitId: recommendation.unitId,
    );

    if (result.success) {
      // Update call status in Firebase RTDB with dispatched unit and active ETA
      // (Requirement 6.4).
      await firebaseService.confirmDispatch(callId, recommendation.unitId);

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                'Dispatched ${recommendation.unitId} — ETA ${recommendation.etaMinutes.toStringAsFixed(0)} min'),
            backgroundColor: Colors.green.shade700,
          ),
        );
      }
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                'Dispatch failed: ${result.errorMessage ?? "Unknown error"}'),
            backgroundColor: Colors.red.shade700,
          ),
        );
      }
    }

    provider.setDispatching(false);
  }

  static IconData _unitTypeIcon(String unitType) {
    return switch (unitType) {
      'ambulance' => Icons.local_hospital,
      'fire_brigade' => Icons.local_fire_department,
      'police' => Icons.local_police,
      _ => Icons.directions_car,
    };
  }

  static String _unitTypeLabel(String unitType) {
    return switch (unitType) {
      'ambulance' => 'Ambulance',
      'fire_brigade' => 'Fire Brigade',
      'police' => 'Police',
      _ => unitType,
    };
  }
}

/// Small metric chip used in recommendation tiles.
class _MetricChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final MaterialColor? color;

  const _MetricChip({
    required this.icon,
    required this.label,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final chipColor = color ?? Colors.grey;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: chipColor.shade50,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: chipColor.shade200),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: chipColor.shade700),
          const SizedBox(width: 3),
          Text(
            label,
            style: TextStyle(fontSize: 11, color: chipColor.shade800),
          ),
        ],
      ),
    );
  }
}

/// Placeholder shown while waiting for dispatch recommendations.
class _WaitingForDispatch extends StatelessWidget {
  const _WaitingForDispatch();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 24),
      child: Center(
        child: Column(
          children: [
            CircularProgressIndicator(strokeWidth: 2),
            SizedBox(height: 12),
            Text(
              'Waiting for dispatch recommendations…',
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }
}

/// Message shown when no units are available.
class _NoUnitsAvailable extends StatelessWidget {
  const _NoUnitsAvailable();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.red.shade300),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: Colors.red.shade700),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'No response units available. Manual dispatch required.',
              style: TextStyle(color: Colors.red.shade800),
            ),
          ),
        ],
      ),
    );
  }
}
