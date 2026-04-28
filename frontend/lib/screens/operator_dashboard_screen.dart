/// Operator Dashboard main screen.
///
/// Composes all dashboard widgets into a responsive layout:
/// - Connection banner (top)
/// - Timeout alert
/// - Error notifications
/// - Triage Card with progressive updates
/// - Dispatch Card with one-tap confirm
/// - Guidance status
/// - Classification override
/// - Live transcript panel
///
/// Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.4, 11.6
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/call_provider.dart';
import '../services/audit_service.dart';
import '../services/dispatch_api_service.dart';
import '../widgets/classification_override.dart';
import '../widgets/connection_banner.dart';
import '../widgets/dispatch_card_widget.dart';
import '../widgets/error_notification.dart';
import '../widgets/guidance_status.dart';
import '../widgets/timeout_alert.dart';
import '../widgets/triage_card.dart';

/// Main Operator Dashboard screen.
class OperatorDashboardScreen extends StatefulWidget {
  final DispatchApiService dispatchApiService;
  final AuditService auditService;
  final String operatorId;

  const OperatorDashboardScreen({
    super.key,
    required this.dispatchApiService,
    required this.auditService,
    required this.operatorId,
  });

  @override
  State<OperatorDashboardScreen> createState() =>
      _OperatorDashboardScreenState();
}

class _OperatorDashboardScreenState extends State<OperatorDashboardScreen> {
  final TextEditingController _callIdController = TextEditingController();

  @override
  void dispose() {
    _callIdController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CrisisLink — Operator Dashboard'),
        centerTitle: false,
        actions: [
          // Call ID input for subscribing to a call
          SizedBox(
            width: 200,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: TextField(
                controller: _callIdController,
                decoration: InputDecoration(
                  hintText: 'Call ID',
                  isDense: true,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  filled: true,
                  fillColor: Colors.white,
                ),
                style: const TextStyle(fontSize: 14),
                onSubmitted: _subscribeToCall,
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            onPressed: () => _subscribeToCall(_callIdController.text),
            icon: const Icon(Icons.phone_in_talk),
            tooltip: 'Connect to call',
          ),
          const SizedBox(width: 8),
          Consumer<CallProvider>(
            builder: (context, provider, _) {
              if (provider.activeCallId == null) {
                return const SizedBox.shrink();
              }
              return IconButton(
                onPressed: provider.disconnectCall,
                icon: const Icon(Icons.phone_disabled),
                tooltip: 'Disconnect',
              );
            },
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          // Connection banner at the very top (Requirement 11.6)
          const ConnectionBanner(),

          // Main content
          Expanded(
            child: Consumer<CallProvider>(
              builder: (context, provider, _) {
                if (provider.activeCallId == null) {
                  return const _NoActiveCall();
                }

                return _DashboardContent(
                  dispatchApiService: widget.dispatchApiService,
                  auditService: widget.auditService,
                  operatorId: widget.operatorId,
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  void _subscribeToCall(String callId) {
    final trimmed = callId.trim();
    if (trimmed.isEmpty) return;

    context.read<CallProvider>().subscribeToCall(trimmed);
  }
}

/// Main dashboard content layout when a call is active.
class _DashboardContent extends StatelessWidget {
  final DispatchApiService dispatchApiService;
  final AuditService auditService;
  final String operatorId;

  const _DashboardContent({
    required this.dispatchApiService,
    required this.auditService,
    required this.operatorId,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // Use a two-column layout on wide screens, single column on narrow.
        final isWide = constraints.maxWidth > 900;

        if (isWide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Left column: alerts + triage + guidance
              Expanded(
                flex: 3,
                child: _LeftColumn(
                  auditService: auditService,
                  operatorId: operatorId,
                ),
              ),
              const SizedBox(width: 16),
              // Right column: dispatch + transcript
              Expanded(
                flex: 2,
                child: _RightColumn(
                  dispatchApiService: dispatchApiService,
                ),
              ),
            ],
          );
        }

        // Single column for narrow screens.
        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              const ErrorNotification(),
              const TimeoutAlert(),
              const SizedBox(height: 8),
              const TriageCard(),
              const SizedBox(height: 8),
              DispatchCardWidget(dispatchApiService: dispatchApiService),
              const SizedBox(height: 8),
              const GuidanceStatusWidget(),
              const SizedBox(height: 8),
              ClassificationOverride(
                auditService: auditService,
                operatorId: operatorId,
              ),
              const SizedBox(height: 8),
              const _TranscriptPanel(),
            ],
          ),
        );
      },
    );
  }
}

/// Left column: alerts, triage card, guidance, override.
class _LeftColumn extends StatelessWidget {
  final AuditService auditService;
  final String operatorId;

  const _LeftColumn({
    required this.auditService,
    required this.operatorId,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          const ErrorNotification(),
          const TimeoutAlert(),
          const SizedBox(height: 8),
          const TriageCard(),
          const SizedBox(height: 8),
          const GuidanceStatusWidget(),
          const SizedBox(height: 8),
          ClassificationOverride(
            auditService: auditService,
            operatorId: operatorId,
          ),
        ],
      ),
    );
  }
}

/// Right column: dispatch card and live transcript.
class _RightColumn extends StatelessWidget {
  final DispatchApiService dispatchApiService;

  const _RightColumn({required this.dispatchApiService});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          DispatchCardWidget(dispatchApiService: dispatchApiService),
          const SizedBox(height: 8),
          const _TranscriptPanel(),
        ],
      ),
    );
  }
}

/// Live transcript display panel.
class _TranscriptPanel extends StatelessWidget {
  const _TranscriptPanel();

  @override
  Widget build(BuildContext context) {
    return Consumer<CallProvider>(
      builder: (context, provider, _) {
        return Card(
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Icon(Icons.mic,
                        color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Live Transcript',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                    const Spacer(),
                    Text(
                      'Call: ${provider.activeCallId ?? "—"}',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
                const Divider(height: 24),
                Container(
                  width: double.infinity,
                  constraints: const BoxConstraints(
                    minHeight: 100,
                    maxHeight: 300,
                  ),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: SingleChildScrollView(
                    child: SelectableText(
                      provider.transcript.isNotEmpty
                          ? provider.transcript
                          : 'Waiting for transcript…',
                      style: TextStyle(
                        fontSize: 14,
                        height: 1.5,
                        color: provider.transcript.isNotEmpty
                            ? Colors.black87
                            : Colors.grey,
                      ),
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
}

/// Placeholder shown when no call is active.
class _NoActiveCall extends StatelessWidget {
  const _NoActiveCall();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.phone_in_talk, size: 64, color: Colors.grey.shade300),
          const SizedBox(height: 16),
          Text(
            'No active call',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.grey.shade500,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Enter a Call ID in the toolbar to connect.',
            style: TextStyle(color: Colors.grey.shade400),
          ),
        ],
      ),
    );
  }
}
