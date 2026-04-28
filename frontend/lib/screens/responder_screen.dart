/// Responder App main screen.
///
/// Composes the dispatch detail view, status transition buttons, and
/// GPS status indicator into a mobile-friendly layout. Allows the
/// responder to enter their unit ID to start the session.
///
/// Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/responder_provider.dart';
import '../widgets/dispatch_detail_view.dart';
import '../widgets/gps_status_indicator.dart';
import '../widgets/status_transition_buttons.dart';

/// Main screen for the Responder App.
///
/// When no unit is connected, shows a unit ID entry form.
/// When connected, shows the dispatch detail, status buttons, and GPS status.
class ResponderScreen extends StatefulWidget {
  const ResponderScreen({super.key});

  @override
  State<ResponderScreen> createState() => _ResponderScreenState();
}

class _ResponderScreenState extends State<ResponderScreen> {
  final TextEditingController _unitIdController = TextEditingController();

  @override
  void dispose() {
    _unitIdController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CrisisLink — Responder'),
        centerTitle: false,
        actions: [
          Consumer<ResponderProvider>(
            builder: (context, provider, _) {
              if (provider.unitId == null) return const SizedBox.shrink();

              return Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Connection indicator
                  Icon(
                    provider.isConnected
                        ? Icons.cloud_done
                        : Icons.cloud_off,
                    color: provider.isConnected
                        ? Colors.green.shade400
                        : Colors.red.shade400,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    provider.unitId!,
                    style: const TextStyle(fontSize: 14),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    onPressed: provider.disconnect,
                    icon: const Icon(Icons.logout),
                    tooltip: 'Disconnect',
                  ),
                ],
              );
            },
          ),
        ],
      ),
      body: Consumer<ResponderProvider>(
        builder: (context, provider, _) {
          if (provider.unitId == null) {
            return _UnitIdEntry(
              controller: _unitIdController,
              onConnect: _connectUnit,
            );
          }

          return _ResponderContent();
        },
      ),
    );
  }

  void _connectUnit(String unitId) {
    final trimmed = unitId.trim();
    if (trimmed.isEmpty) return;

    context.read<ResponderProvider>().initialize(trimmed);
  }
}

/// Unit ID entry form shown before the responder connects.
class _UnitIdEntry extends StatelessWidget {
  final TextEditingController controller;
  final void Function(String) onConnect;

  const _UnitIdEntry({
    required this.controller,
    required this.onConnect,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.local_shipping,
                size: 72, color: Colors.blue.shade200),
            const SizedBox(height: 24),
            Text(
              'Responder Login',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Enter your unit ID to start receiving dispatch assignments.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey.shade600),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: 280,
              child: TextField(
                controller: controller,
                decoration: InputDecoration(
                  labelText: 'Unit ID',
                  hintText: 'e.g., AMB_007',
                  prefixIcon: const Icon(Icons.badge),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                textInputAction: TextInputAction.go,
                onSubmitted: onConnect,
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: 280,
              child: ElevatedButton.icon(
                onPressed: () => onConnect(controller.text),
                icon: const Icon(Icons.login),
                label: const Text('Connect'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  textStyle: const TextStyle(fontSize: 16),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Main responder content when a unit is connected.
class _ResponderContent extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<ResponderProvider>(
      builder: (context, provider, _) {
        // If there's an active dispatch, show the dispatch detail view
        // with status buttons and GPS indicator below.
        if (provider.hasActiveDispatch) {
          return Column(
            children: [
              // Dispatch detail (map + case context) takes most of the space
              const Expanded(
                flex: 3,
                child: DispatchDetailView(),
              ),

              // Bottom panel: status buttons + GPS indicator
              Container(
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 8,
                      offset: const Offset(0, -2),
                    ),
                  ],
                ),
                child: const SingleChildScrollView(
                  padding: EdgeInsets.all(12),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      StatusTransitionButtons(),
                      SizedBox(height: 8),
                      GpsStatusIndicator(),
                    ],
                  ),
                ),
              ),
            ],
          );
        }

        // No active dispatch — show status and GPS in a centered layout.
        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              // Waiting for dispatch
              Card(
                elevation: 2,
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    children: [
                      Icon(
                        Icons.notifications_active,
                        size: 48,
                        color: Colors.blue.shade200,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Standing By',
                        style: Theme.of(context)
                            .textTheme
                            .headlineSmall
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'You will receive a push notification when a '
                        'dispatch is assigned to your unit.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.grey.shade600),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              const StatusTransitionButtons(),
              const SizedBox(height: 12),
              const GpsStatusIndicator(),
            ],
          ),
        );
      },
    );
  }
}
