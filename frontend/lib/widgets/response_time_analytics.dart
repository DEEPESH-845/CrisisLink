/// Response time analytics widget for the Admin Dashboard.
///
/// Displays response time metrics broken down by region, time of day,
/// and emergency type. Data is sourced from BigQuery via the analytics
/// backend.
///
/// Requirements: 9.3
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/admin_provider.dart';
import '../services/analytics_service.dart';

/// Response time analytics display with tabbed breakdown views.
class ResponseTimeAnalytics extends StatefulWidget {
  const ResponseTimeAnalytics({super.key});

  @override
  State<ResponseTimeAnalytics> createState() => _ResponseTimeAnalyticsState();
}

class _ResponseTimeAnalyticsState extends State<ResponseTimeAnalytics>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  static const _tabs = ['By Region', 'By Time of Day', 'By Emergency Type'];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AdminProvider>(
      builder: (context, provider, _) {
        return Card(
          elevation: 2,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                child: Row(
                  children: [
                    Icon(Icons.timer,
                        color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Response Time Analytics',
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

              // Tabs
              TabBar(
                controller: _tabController,
                tabs: _tabs.map((t) => Tab(text: t)).toList(),
                labelStyle: const TextStyle(fontSize: 13),
                isScrollable: true,
              ),

              // Tab content
              Expanded(
                child: TabBarView(
                  controller: _tabController,
                  children: [
                    _ResponseTimeTable(
                        entries: provider.responseTimesByRegion),
                    _ResponseTimeTable(
                        entries: provider.responseTimesByTimeOfDay),
                    _ResponseTimeTable(
                        entries: provider.responseTimesByEmergencyType),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Table displaying response time entries for a single breakdown dimension.
class _ResponseTimeTable extends StatelessWidget {
  final List<ResponseTimeEntry> entries;

  const _ResponseTimeTable({required this.entries});

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) {
      return const Center(
        child: Text(
          'No response time data available',
          style: TextStyle(color: Colors.grey),
        ),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(8),
      child: DataTable(
        columnSpacing: 20,
        headingRowHeight: 40,
        dataRowMinHeight: 36,
        dataRowMaxHeight: 44,
        columns: const [
          DataColumn(label: Text('Dimension')),
          DataColumn(label: Text('Avg (min)'), numeric: true),
          DataColumn(label: Text('Median (min)'), numeric: true),
          DataColumn(label: Text('P95 (min)'), numeric: true),
          DataColumn(label: Text('Incidents'), numeric: true),
        ],
        rows: entries.map((entry) {
          return DataRow(cells: [
            DataCell(Text(
              entry.dimension,
              style: const TextStyle(fontWeight: FontWeight.w500),
            )),
            DataCell(Text(entry.avgResponseMinutes.toStringAsFixed(1))),
            DataCell(Text(entry.medianResponseMinutes.toStringAsFixed(1))),
            DataCell(_P95Cell(value: entry.p95ResponseMinutes)),
            DataCell(Text(entry.totalIncidents.toString())),
          ]);
        }).toList(),
      ),
    );
  }
}

/// P95 cell with color coding: green < 10min, orange 10–20min, red > 20min.
class _P95Cell extends StatelessWidget {
  final double value;

  const _P95Cell({required this.value});

  @override
  Widget build(BuildContext context) {
    final color = value < 10
        ? Colors.green
        : value < 20
            ? Colors.orange
            : Colors.red;

    return Text(
      value.toStringAsFixed(1),
      style: TextStyle(
        color: color,
        fontWeight: FontWeight.w600,
      ),
    );
  }
}
