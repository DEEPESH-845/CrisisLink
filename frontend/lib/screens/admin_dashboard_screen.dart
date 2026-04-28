/// Admin Dashboard screen for PSAP administrators.
///
/// Provides a unified view of live incident data, unit availability,
/// response time analytics, classification accuracy monitoring, and
/// Vertex AI trend reports.
///
/// Layout: Two-column responsive layout.
///   Left column: Incident heatmap (top), Unit availability (bottom).
///   Right column: Response time analytics, Classification accuracy,
///                 Trend reports.
///
/// Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/admin_provider.dart';
import '../services/admin_firebase_service.dart';
import '../services/analytics_service.dart';
import '../widgets/classification_accuracy.dart';
import '../widgets/incident_heatmap.dart';
import '../widgets/response_time_analytics.dart';
import '../widgets/trend_reports.dart';
import '../widgets/unit_availability_overview.dart';

/// Main Admin Dashboard screen.
class AdminDashboardScreen extends StatefulWidget {
  final AdminFirebaseService adminFirebaseService;
  final AnalyticsService analyticsService;

  const AdminDashboardScreen({
    super.key,
    required this.adminFirebaseService,
    required this.analyticsService,
  });

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  late final AdminProvider _adminProvider;

  @override
  void initState() {
    super.initState();
    _adminProvider = AdminProvider(
      firebaseService: widget.adminFirebaseService,
      analyticsService: widget.analyticsService,
    );
    // Start listening to live Firebase data.
    _adminProvider.startListening();
    // Fetch initial analytics data.
    _adminProvider.fetchAnalytics();
  }

  @override
  void dispose() {
    _adminProvider.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<AdminProvider>.value(
      value: _adminProvider,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('CrisisLink — Admin Dashboard'),
          actions: [
            // Connection indicator
            Consumer<AdminProvider>(
              builder: (context, provider, _) {
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: provider.isConnected
                              ? Colors.green
                              : Colors.red,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        provider.isConnected ? 'Connected' : 'Disconnected',
                        style: const TextStyle(fontSize: 12),
                      ),
                    ],
                  ),
                );
              },
            ),

            // Refresh analytics button
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh Analytics',
              onPressed: () => _adminProvider.refreshAnalytics(),
            ),
            const SizedBox(width: 8),
          ],
        ),
        body: _AdminDashboardBody(),
      ),
    );
  }
}

/// Dashboard body with responsive two-column layout.
class _AdminDashboardBody extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<AdminProvider>(
      builder: (context, provider, _) {
        // Show error banner if analytics failed.
        return Column(
          children: [
            if (provider.analyticsError != null)
              MaterialBanner(
                content: Text(provider.analyticsError!),
                backgroundColor: Colors.orange.shade50,
                leading: const Icon(Icons.warning, color: Colors.orange),
                actions: [
                  TextButton(
                    onPressed: () => provider.refreshAnalytics(),
                    child: const Text('Retry'),
                  ),
                ],
              ),

            if (!provider.isConnected)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 6),
                color: Colors.orange.shade100,
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    SizedBox(width: 8),
                    Text(
                      'Reconnecting to Firebase…',
                      style: TextStyle(fontSize: 13),
                    ),
                  ],
                ),
              ),

            // Main content
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  // Use single column on narrow screens.
                  if (constraints.maxWidth < 900) {
                    return _SingleColumnLayout();
                  }
                  return _TwoColumnLayout();
                },
              ),
            ),
          ],
        );
      },
    );
  }
}

/// Two-column layout for wide screens.
class _TwoColumnLayout extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Left column: Live data (heatmap + unit overview)
          Expanded(
            flex: 3,
            child: Column(
              children: [
                // Incident heatmap
                const Expanded(
                  flex: 3,
                  child: IncidentHeatmap(),
                ),
                const SizedBox(height: 16),
                // Unit availability
                const Expanded(
                  flex: 2,
                  child: UnitAvailabilityOverview(),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),

          // Right column: Analytics
          Expanded(
            flex: 2,
            child: SingleChildScrollView(
              child: Column(
                children: [
                  // Response time analytics
                  const SizedBox(
                    height: 350,
                    child: ResponseTimeAnalytics(),
                  ),
                  const SizedBox(height: 16),

                  // Classification accuracy
                  const ClassificationAccuracy(),
                  const SizedBox(height: 16),

                  // Trend reports
                  const SizedBox(
                    height: 400,
                    child: TrendReports(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Single-column layout for narrow screens.
class _SingleColumnLayout extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Incident heatmap
          const SizedBox(
            height: 400,
            child: IncidentHeatmap(),
          ),
          const SizedBox(height: 16),

          // Unit availability
          const SizedBox(
            height: 350,
            child: UnitAvailabilityOverview(),
          ),
          const SizedBox(height: 16),

          // Response time analytics
          const SizedBox(
            height: 350,
            child: ResponseTimeAnalytics(),
          ),
          const SizedBox(height: 16),

          // Classification accuracy
          const ClassificationAccuracy(),
          const SizedBox(height: 16),

          // Trend reports
          const SizedBox(
            height: 400,
            child: TrendReports(),
          ),
        ],
      ),
    );
  }
}
