/// Guidance status display widget.
///
/// Shows current guidance status (generating, active, completed),
/// language, and protocol type.
///
/// Requirements: 6.5
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/call_session.dart';
import '../providers/call_provider.dart';

/// Displays the current caller guidance generation status.
class GuidanceStatusWidget extends StatelessWidget {
  const GuidanceStatusWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<CallProvider>(
      builder: (context, provider, _) {
        final guidance = provider.guidance;

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
                      Icons.support_agent,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Caller Guidance',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                    const Spacer(),
                    if (guidance != null)
                      _StatusBadge(status: guidance.status),
                  ],
                ),
                const Divider(height: 24),

                if (guidance == null ||
                    guidance.status == GuidanceStatus.notApplicable)
                  const _NoGuidance()
                else ...[
                  // Status indicator with animation for generating state
                  _GuidanceDetail(
                    icon: Icons.play_circle_outline,
                    label: 'Status',
                    value: _statusLabel(guidance.status),
                    trailing: guidance.status == GuidanceStatus.generating
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : null,
                  ),
                  const SizedBox(height: 8),

                  // Language
                  _GuidanceDetail(
                    icon: Icons.language,
                    label: 'Language',
                    value: guidance.language.isNotEmpty
                        ? guidance.language
                        : 'Detecting…',
                  ),
                  const SizedBox(height: 8),

                  // Protocol type
                  _GuidanceDetail(
                    icon: Icons.menu_book,
                    label: 'Protocol',
                    value: _protocolLabel(guidance.protocolType),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  static String _statusLabel(GuidanceStatus status) {
    return switch (status) {
      GuidanceStatus.generating => 'Generating…',
      GuidanceStatus.active => 'Active — Speaking to caller',
      GuidanceStatus.completed => 'Completed',
      GuidanceStatus.notApplicable => 'Not applicable',
    };
  }

  static String _protocolLabel(String protocolType) {
    if (protocolType.isEmpty) return 'Determining…';
    return switch (protocolType) {
      'CPR_IRC_2022' => 'CPR — Indian Resuscitation Council 2022',
      'FIRE_NDMA' => 'Fire Evacuation — NDMA India',
      _ => protocolType.replaceAll('_', ' '),
    };
  }
}

/// Badge showing the guidance status with color coding.
class _StatusBadge extends StatelessWidget {
  final GuidanceStatus status;

  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final (color, label) = switch (status) {
      GuidanceStatus.generating => (Colors.blue, 'Generating'),
      GuidanceStatus.active => (Colors.green, 'Active'),
      GuidanceStatus.completed => (Colors.grey, 'Completed'),
      GuidanceStatus.notApplicable => (Colors.grey, 'N/A'),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.shade50,
        border: Border.all(color: color.shade400),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: color.shade800,
        ),
      ),
    );
  }
}

/// Detail row for guidance information.
class _GuidanceDetail extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Widget? trailing;

  const _GuidanceDetail({
    required this.icon,
    required this.label,
    required this.value,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: Colors.grey.shade600),
        const SizedBox(width: 8),
        Text(
          '$label: ',
          style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

/// Placeholder when no guidance is active.
class _NoGuidance extends StatelessWidget {
  const _NoGuidance();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Center(
        child: Text(
          'No active guidance — severity below threshold or awaiting classification.',
          style: TextStyle(color: Colors.grey.shade500, fontSize: 13),
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}
