/// Vertex AI trend reports widget for the Admin Dashboard.
///
/// Displays predictive unit pre-positioning recommendations based on
/// historical incident patterns analyzed by Vertex AI.
///
/// Requirements: 9.5
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/admin_provider.dart';
import '../services/analytics_service.dart';

/// Vertex AI trend reports display for predictive unit pre-positioning.
class TrendReports extends StatelessWidget {
  const TrendReports({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AdminProvider>(
      builder: (context, provider, _) {
        final reports = provider.trendReports;

        return Card(
          elevation: 2,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Icon(Icons.trending_up,
                        color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Vertex AI Trend Reports',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                    const Spacer(),
                    if (provider.isLoadingAnalytics)
                      const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                  ],
                ),
              ),
              const Divider(height: 1),

              // Reports list
              Expanded(
                child: reports.isEmpty
                    ? const Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.insights,
                                size: 48, color: Colors.grey),
                            SizedBox(height: 8),
                            Text(
                              'No trend reports available',
                              style: TextStyle(color: Colors.grey),
                            ),
                            SizedBox(height: 4),
                            Text(
                              'Vertex AI predictions will appear here',
                              style: TextStyle(
                                  color: Colors.grey, fontSize: 12),
                            ),
                          ],
                        ),
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.all(12),
                        itemCount: reports.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(height: 8),
                        itemBuilder: (context, index) {
                          return _TrendReportCard(report: reports[index]);
                        },
                      ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Individual trend report card.
class _TrendReportCard extends StatelessWidget {
  final TrendReportEntry report;

  const _TrendReportCard({required this.report});

  @override
  Widget build(BuildContext context) {
    final confidencePercent = (report.confidence * 100).toStringAsFixed(0);
    final confidenceColor = report.confidence >= 0.8
        ? Colors.green
        : report.confidence >= 0.6
            ? Colors.orange
            : Colors.red;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Region and time window
          Row(
            children: [
              Icon(Icons.location_on,
                  size: 16, color: Colors.grey.shade600),
              const SizedBox(width: 4),
              Text(
                report.region,
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
              const SizedBox(width: 12),
              Icon(Icons.schedule,
                  size: 16, color: Colors.grey.shade600),
              const SizedBox(width: 4),
              Text(
                report.timeWindow,
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.grey.shade700,
                ),
              ),
              const Spacer(),
              // Confidence badge
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: confidenceColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '$confidencePercent% confidence',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: confidenceColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Prediction details
          Row(
            children: [
              _PredictionChip(
                label: 'Predicted Type',
                value: report.predictedEmergencyType,
                icon: Icons.warning_amber,
              ),
              const SizedBox(width: 12),
              _PredictionChip(
                label: 'Recommended Units',
                value: report.recommendedUnits.toString(),
                icon: Icons.local_shipping,
              ),
            ],
          ),

          if (report.generatedAt.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              'Generated: ${report.generatedAt}',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
            ),
          ],
        ],
      ),
    );
  }
}

/// Small chip showing a prediction label and value.
class _PredictionChip extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;

  const _PredictionChip({
    required this.label,
    required this.value,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: Colors.grey.shade600),
        const SizedBox(width: 4),
        Text(
          '$label: ',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
        Text(
          value,
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}
