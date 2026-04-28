/// Unit availability overview widget for the Admin Dashboard.
///
/// Displays the current status of all Response_Units in a summary bar
/// and a detailed data table with unit ID, type, status, location, and
/// last updated timestamp.
///
/// Requirements: 9.2
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/response_unit.dart';
import '../providers/admin_provider.dart';

/// Unit availability overview showing current status of all Response_Units.
class UnitAvailabilityOverview extends StatelessWidget {
  const UnitAvailabilityOverview({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AdminProvider>(
      builder: (context, provider, _) {
        final units = provider.units;
        final statusCounts = provider.unitStatusCounts;

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
                    Icon(Icons.local_shipping,
                        color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Unit Availability Overview',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                    const Spacer(),
                    Text(
                      '${units.length} total',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),

              // Status summary bar
              _StatusSummaryBar(statusCounts: statusCounts),

              const Divider(height: 1),

              // Unit table
              Expanded(
                child: units.isEmpty
                    ? const Center(
                        child: Text(
                          'No units registered',
                          style: TextStyle(color: Colors.grey),
                        ),
                      )
                    : _UnitDataTable(units: units),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Horizontal bar showing counts per status.
class _StatusSummaryBar extends StatelessWidget {
  final Map<UnitStatus, int> statusCounts;

  const _StatusSummaryBar({required this.statusCounts});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          _StatusChip(
            label: 'Available',
            count: statusCounts[UnitStatus.available] ?? 0,
            color: Colors.green,
          ),
          const SizedBox(width: 8),
          _StatusChip(
            label: 'Dispatched',
            count: statusCounts[UnitStatus.dispatched] ?? 0,
            color: Colors.orange,
          ),
          const SizedBox(width: 8),
          _StatusChip(
            label: 'On Scene',
            count: statusCounts[UnitStatus.onScene] ?? 0,
            color: Colors.red,
          ),
          const SizedBox(width: 8),
          _StatusChip(
            label: 'Returning',
            count: statusCounts[UnitStatus.returning] ?? 0,
            color: Colors.blue,
          ),
        ],
      ),
    );
  }
}

/// Chip showing a status label and count.
class _StatusChip extends StatelessWidget {
  final String label;
  final int count;
  final Color color;

  const _StatusChip({
    required this.label,
    required this.count,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            '$count $label',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: color.withValues(alpha: 0.87),
            ),
          ),
        ],
      ),
    );
  }
}

/// Scrollable data table of all units.
class _UnitDataTable extends StatelessWidget {
  final List<ResponseUnit> units;

  const _UnitDataTable({required this.units});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: DataTable(
        columnSpacing: 24,
        headingRowHeight: 40,
        dataRowMinHeight: 36,
        dataRowMaxHeight: 44,
        columns: const [
          DataColumn(label: Text('Unit ID')),
          DataColumn(label: Text('Type')),
          DataColumn(label: Text('Status')),
          DataColumn(label: Text('Station')),
          DataColumn(label: Text('Capabilities')),
          DataColumn(label: Text('Last Updated')),
        ],
        rows: units.map((unit) {
          return DataRow(cells: [
            DataCell(Text(
              unit.unitId,
              style: const TextStyle(fontWeight: FontWeight.w500),
            )),
            DataCell(_UnitTypeChip(type: unit.type)),
            DataCell(_UnitStatusIndicator(status: unit.status)),
            DataCell(Text(unit.hospitalOrStation)),
            DataCell(Text(
              unit.capabilities.join(', '),
              overflow: TextOverflow.ellipsis,
            )),
            DataCell(Text(_formatTimestamp(unit.lastUpdated))),
          ]);
        }).toList(),
      ),
    );
  }

  String _formatTimestamp(int unixTimestamp) {
    if (unixTimestamp == 0) return '—';
    final dt = DateTime.fromMillisecondsSinceEpoch(unixTimestamp);
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inSeconds < 60) return '${diff.inSeconds}s ago';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}

/// Colored chip for unit type.
class _UnitTypeChip extends StatelessWidget {
  final UnitType type;

  const _UnitTypeChip({required this.type});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (type) {
      UnitType.ambulance => ('Ambulance', Colors.red),
      UnitType.fireBrigade => ('Fire', Colors.orange),
      UnitType.police => ('Police', Colors.blue),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600),
      ),
    );
  }
}

/// Status indicator with colored dot.
class _UnitStatusIndicator extends StatelessWidget {
  final UnitStatus status;

  const _UnitStatusIndicator({required this.status});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (status) {
      UnitStatus.available => ('Available', Colors.green),
      UnitStatus.dispatched => ('Dispatched', Colors.orange),
      UnitStatus.onScene => ('On Scene', Colors.red),
      UnitStatus.returning => ('Returning', Colors.blue),
    };

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(label, style: TextStyle(fontSize: 13, color: color)),
      ],
    );
  }
}
