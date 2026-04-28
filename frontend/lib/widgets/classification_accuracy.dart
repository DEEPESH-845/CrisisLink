/// Classification accuracy monitoring widget for the Admin Dashboard.
///
/// Displays false classification rate metrics derived from operator override
/// frequency. Operator overrides are recorded as negative labels for
/// classification accuracy monitoring.
///
/// Property 11: rate = overrides / total_classifications,
///   rate ∈ [0.0, 1.0], rate = 0.0 when total is zero.
///
/// Requirements: 9.4, 9.6
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/admin_provider.dart';
import '../services/analytics_service.dart';

/// Classification accuracy display with false classification rate metric.
class ClassificationAccuracy extends StatelessWidget {
  const ClassificationAccuracy({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AdminProvider>(
      builder: (context, provider, _) {
        final metrics = provider.classificationAccuracy;

        return Card(
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  children: [
                    Icon(Icons.analytics,
                        color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Classification Accuracy',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                  ],
                ),
                const Divider(height: 24),

                // False classification rate — primary metric
                _FalseClassificationRateDisplay(metrics: metrics),

                const SizedBox(height: 16),

                // Breakdown stats
                Row(
                  children: [
                    Expanded(
                      child: _MetricTile(
                        label: 'Total Classifications',
                        value: metrics.totalClassifications.toString(),
                        icon: Icons.check_circle_outline,
                        color: Colors.blue,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _MetricTile(
                        label: 'Operator Overrides',
                        value: metrics.operatorOverrides.toString(),
                        icon: Icons.edit_note,
                        color: Colors.orange,
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 12),

                // Explanation
                Text(
                  'Operator overrides are recorded as negative labels. '
                  'The false classification rate is computed as '
                  'overrides ÷ total classifications.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey.shade600,
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

/// Large display of the false classification rate with color coding.
class _FalseClassificationRateDisplay extends StatelessWidget {
  final ClassificationAccuracyMetrics metrics;

  const _FalseClassificationRateDisplay({required this.metrics});

  @override
  Widget build(BuildContext context) {
    final rate = metrics.falseClassificationRate;
    final percentage = (rate * 100).toStringAsFixed(1);

    // Color coding: green < 5%, orange 5–15%, red > 15%.
    final color = rate < 0.05
        ? Colors.green
        : rate < 0.15
            ? Colors.orange
            : Colors.red;

    final qualityLabel = rate < 0.05
        ? 'Excellent'
        : rate < 0.15
            ? 'Acceptable'
            : 'Needs Attention';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text(
            'False Classification Rate',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Colors.grey.shade700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '$percentage%',
            style: TextStyle(
              fontSize: 36,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              qualityLabel,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Small metric tile with icon, label, and value.
class _MetricTile extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _MetricTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Icon(icon, size: 20, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey.shade600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
