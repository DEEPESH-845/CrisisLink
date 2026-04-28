/// Triage Card widget with progressive streaming updates.
///
/// Displays emergency type, severity, confidence score, caller state
/// (panic level and role), detected language, and extracted key facts.
/// Shows low-confidence alert (confidence < 0.7) and INCOHERENT caller
/// state alert.
///
/// Requirements: 6.2, 6.6, 2.6, 3.3
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/emergency_classification.dart';
import '../providers/call_provider.dart';

/// Triage Card displaying the AI emergency classification with progressive
/// streaming updates as the Intelligence Engine writes token-by-token.
class TriageCard extends StatelessWidget {
  const TriageCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<CallProvider>(
      builder: (context, provider, _) {
        final classification = provider.classification;
        final callerState = provider.callerState;

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
                      Icons.assignment,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Triage Card',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const Spacer(),
                    if (classification != null)
                      _ConfidenceBadge(confidence: classification.confidence),
                  ],
                ),
                const Divider(height: 24),

                // Low-confidence alert (Requirement 6.6, 2.6)
                if (provider.isLowConfidence) ...[
                  const _LowConfidenceAlert(),
                  const SizedBox(height: 12),
                ],

                // INCOHERENT caller state alert (Requirement 3.3)
                if (provider.isCallerIncoherent) ...[
                  const _IncoherentAlert(),
                  const SizedBox(height: 12),
                ],

                if (classification == null)
                  const _StreamingPlaceholder()
                else ...[
                  // Emergency type and severity
                  _InfoRow(
                    label: 'Emergency Type',
                    value: classification.emergencyType.value,
                    icon: _emergencyTypeIcon(classification.emergencyType),
                    color: _severityColor(classification.severity),
                  ),
                  const SizedBox(height: 8),
                  _InfoRow(
                    label: 'Severity',
                    value: classification.severity.value,
                    icon: Icons.warning_amber_rounded,
                    color: _severityColor(classification.severity),
                  ),
                  const SizedBox(height: 8),

                  // Caller state
                  if (callerState != null) ...[
                    _InfoRow(
                      label: 'Panic Level',
                      value: callerState.panicLevel.value,
                      icon: Icons.psychology,
                      color: _panicColor(callerState.panicLevel),
                    ),
                    const SizedBox(height: 8),
                    _InfoRow(
                      label: 'Caller Role',
                      value: callerState.callerRole.value,
                      icon: Icons.person,
                    ),
                    const SizedBox(height: 8),
                  ],

                  // Language
                  _InfoRow(
                    label: 'Language',
                    value: classification.languageDetected,
                    icon: Icons.language,
                  ),
                  const SizedBox(height: 12),

                  // Key facts
                  if (classification.keyFacts.isNotEmpty) ...[
                    Text(
                      'Key Facts',
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: classification.keyFacts
                          .map((fact) => Chip(
                                label: Text(fact,
                                    style: const TextStyle(fontSize: 12)),
                                materialTapTargetSize:
                                    MaterialTapTargetSize.shrinkWrap,
                                visualDensity: VisualDensity.compact,
                              ))
                          .toList(),
                    ),
                  ],
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  static IconData _emergencyTypeIcon(EmergencyType type) {
    return switch (type) {
      EmergencyType.medical => Icons.local_hospital,
      EmergencyType.fire => Icons.local_fire_department,
      EmergencyType.crime => Icons.shield,
      EmergencyType.accident => Icons.car_crash,
      EmergencyType.disaster => Icons.flood,
      EmergencyType.unknown => Icons.help_outline,
    };
  }

  static Color _severityColor(Severity severity) {
    return switch (severity) {
      Severity.critical => Colors.red.shade700,
      Severity.high => Colors.orange.shade700,
      Severity.moderate => Colors.amber.shade700,
      Severity.low => Colors.green.shade700,
    };
  }

  static Color _panicColor(PanicLevel level) {
    return switch (level) {
      PanicLevel.panicHigh => Colors.red.shade700,
      PanicLevel.panicMed => Colors.orange.shade600,
      PanicLevel.calm => Colors.green.shade600,
      PanicLevel.incoherent => Colors.purple.shade700,
    };
  }
}

/// Animated placeholder shown while classification is streaming in.
class _StreamingPlaceholder extends StatelessWidget {
  const _StreamingPlaceholder();

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
              'Analyzing call…',
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }
}

/// Low-confidence alert banner (Requirement 6.6, 2.6).
class _LowConfidenceAlert extends StatelessWidget {
  const _LowConfidenceAlert();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.orange.shade50,
        border: Border.all(color: Colors.orange.shade400, width: 2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(Icons.warning_amber_rounded,
              color: Colors.orange.shade700, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Low Confidence Classification',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Colors.orange.shade900,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'AI confidence is below 70%. Please verify and consider manual override.',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.orange.shade800,
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

/// INCOHERENT caller state alert (Requirement 3.3).
class _IncoherentAlert extends StatelessWidget {
  const _IncoherentAlert();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.purple.shade50,
        border: Border.all(color: Colors.purple.shade400, width: 2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(Icons.record_voice_over,
              color: Colors.purple.shade700, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Caller Incoherent',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Colors.purple.shade900,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Caller speech is incoherent. Recommend taking direct control of the call.',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.purple.shade800,
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

/// Confidence score badge with color coding.
class _ConfidenceBadge extends StatelessWidget {
  final double confidence;

  const _ConfidenceBadge({required this.confidence});

  @override
  Widget build(BuildContext context) {
    final percentage = (confidence * 100).toStringAsFixed(0);
    final color = confidence >= 0.7 ? Colors.green : Colors.orange;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.shade50,
        border: Border.all(color: color.shade400),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '$percentage% confidence',
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: color.shade800,
        ),
      ),
    );
  }
}

/// A single labeled info row used in the triage card.
class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color? color;

  const _InfoRow({
    required this.label,
    required this.value,
    required this.icon,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: color ?? Colors.grey.shade600),
        const SizedBox(width: 8),
        Text(
          '$label: ',
          style: TextStyle(
            fontSize: 13,
            color: Colors.grey.shade600,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: color ?? Theme.of(context).colorScheme.onSurface,
          ),
        ),
      ],
    );
  }
}
