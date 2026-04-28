/// Classification override UI widget.
///
/// Allows operator to manually select a different emergency type or severity,
/// overriding the AI classification. Writes override events to BigQuery
/// audit log.
///
/// Requirements: 6.7, 10.4
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/emergency_classification.dart';
import '../providers/call_provider.dart';
import '../services/audit_service.dart';
import '../services/firebase_service.dart';

/// Classification override panel allowing operator to change emergency type
/// or severity.
class ClassificationOverride extends StatefulWidget {
  final AuditService auditService;
  final String operatorId;

  const ClassificationOverride({
    super.key,
    required this.auditService,
    required this.operatorId,
  });

  @override
  State<ClassificationOverride> createState() =>
      _ClassificationOverrideState();
}

class _ClassificationOverrideState extends State<ClassificationOverride> {
  EmergencyType? _selectedType;
  Severity? _selectedSeverity;
  bool _isSubmitting = false;

  @override
  Widget build(BuildContext context) {
    return Consumer<CallProvider>(
      builder: (context, provider, _) {
        final classification = provider.classification;
        if (classification == null) return const SizedBox.shrink();

        // Initialize dropdowns with current values.
        _selectedType ??= classification.emergencyType;
        _selectedSeverity ??= classification.severity;

        final hasChanges = _selectedType != classification.emergencyType ||
            _selectedSeverity != classification.severity;

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
                      Icons.edit_note,
                      color: Theme.of(context).colorScheme.secondary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Classification Override',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                  ],
                ),
                const Divider(height: 24),

                // Emergency type dropdown
                _OverrideDropdown<EmergencyType>(
                  label: 'Emergency Type',
                  value: _selectedType!,
                  items: EmergencyType.values,
                  itemLabel: (e) => e.value,
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => _selectedType = value);
                    }
                  },
                ),
                const SizedBox(height: 12),

                // Severity dropdown
                _OverrideDropdown<Severity>(
                  label: 'Severity',
                  value: _selectedSeverity!,
                  items: Severity.values,
                  itemLabel: (e) => e.value,
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => _selectedSeverity = value);
                    }
                  },
                ),
                const SizedBox(height: 16),

                // Submit override button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: hasChanges && !_isSubmitting
                        ? () => _submitOverride(context, classification)
                        : null,
                    icon: _isSubmitting
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.check),
                    label: Text(
                        _isSubmitting ? 'Submitting…' : 'Apply Override'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          Theme.of(context).colorScheme.secondary,
                      foregroundColor:
                          Theme.of(context).colorScheme.onSecondary,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  /// Submit the classification override.
  ///
  /// 1. Build the overridden classification.
  /// 2. Write to Firebase RTDB.
  /// 3. Log override event to BigQuery audit log (Requirement 10.4).
  Future<void> _submitOverride(
    BuildContext context,
    EmergencyClassification original,
  ) async {
    setState(() => _isSubmitting = true);

    final overridden = EmergencyClassification(
      callId: original.callId,
      emergencyType: _selectedType!,
      severity: _selectedSeverity!,
      callerState: original.callerState,
      languageDetected: original.languageDetected,
      keyFacts: original.keyFacts,
      confidence: original.confidence,
      timestamp: DateTime.now().toUtc().toIso8601String(),
      modelVersion: 'operator_override',
    );

    final provider = context.read<CallProvider>();
    final firebaseService = context.read<FirebaseService>();

    // Write override to Firebase RTDB.
    await firebaseService.writeClassificationOverride(
      original.callId,
      overridden,
    );

    // Update local state.
    provider.overrideClassification(overridden);

    // Log to BigQuery audit log (Requirement 10.4).
    await widget.auditService.logClassificationOverride(
      callId: original.callId,
      operatorId: widget.operatorId,
      originalClassification: original.toJson(),
      overriddenClassification: overridden.toJson(),
    );

    if (mounted) {
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Classification overridden successfully'),
          backgroundColor: Colors.green,
        ),
      );
    }
  }
}

/// Generic dropdown for override selections.
class _OverrideDropdown<T> extends StatelessWidget {
  final String label;
  final T value;
  final List<T> items;
  final String Function(T) itemLabel;
  final ValueChanged<T?> onChanged;

  const _OverrideDropdown({
    required this.label,
    required this.value,
    required this.items,
    required this.itemLabel,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: Colors.grey.shade700,
          ),
        ),
        const SizedBox(height: 4),
        DropdownButtonFormField<T>(
          value: value,
          decoration: InputDecoration(
            border: const OutlineInputBorder(),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            isDense: true,
            filled: true,
            fillColor: Colors.grey.shade50,
          ),
          items: items
              .map((item) => DropdownMenuItem<T>(
                    value: item,
                    child: Text(itemLabel(item), style: const TextStyle(fontSize: 14)),
                  ))
              .toList(),
          onChanged: onChanged,
        ),
      ],
    );
  }
}
