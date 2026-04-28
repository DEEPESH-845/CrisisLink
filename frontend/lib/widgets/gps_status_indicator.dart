/// GPS tracking status indicator for the Responder App.
///
/// Displays the current GPS tracking status and alerts the responder
/// when location data becomes stale (no update for > 30 seconds) or
/// when GPS permissions are denied.
///
/// Requirements: 7.6, 8.1
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/gps_service.dart';

/// Compact GPS status indicator widget.
///
/// Shows a colored icon and label reflecting the current [GpsTrackingStatus].
/// When the status is [GpsTrackingStatus.stale] or
/// [GpsTrackingStatus.permissionDenied], displays a prominent alert
/// prompting the responder to re-enable location services.
class GpsStatusIndicator extends StatelessWidget {
  const GpsStatusIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<GpsService>(
      builder: (context, gpsService, _) {
        final status = gpsService.status;
        final lastPush = gpsService.lastSuccessfulPush;
        final lastPos = gpsService.lastPosition;

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
                      _statusIcon(status),
                      color: _statusColor(status),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'GPS Tracking',
                      style:
                          Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                    const Spacer(),
                    _StatusChip(status: status),
                  ],
                ),

                // Stale / permission denied alert
                if (status == GpsTrackingStatus.stale ||
                    status == GpsTrackingStatus.permissionDenied) ...[
                  const SizedBox(height: 12),
                  _StaleAlert(status: status),
                ],

                // Last update info
                if (lastPush != null || lastPos != null) ...[
                  const Divider(height: 20),
                  if (lastPos != null)
                    _InfoRow(
                      label: 'Last Position',
                      value:
                          '${lastPos.latitude.toStringAsFixed(5)}, '
                          '${lastPos.longitude.toStringAsFixed(5)}',
                    ),
                  if (lastPush != null)
                    _InfoRow(
                      label: 'Last Update',
                      value: _formatTimestamp(lastPush),
                    ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  IconData _statusIcon(GpsTrackingStatus status) {
    return switch (status) {
      GpsTrackingStatus.active => Icons.gps_fixed,
      GpsTrackingStatus.stopped => Icons.gps_off,
      GpsTrackingStatus.stale => Icons.gps_not_fixed,
      GpsTrackingStatus.permissionDenied => Icons.location_disabled,
    };
  }

  Color _statusColor(GpsTrackingStatus status) {
    return switch (status) {
      GpsTrackingStatus.active => Colors.green.shade700,
      GpsTrackingStatus.stopped => Colors.grey.shade600,
      GpsTrackingStatus.stale => Colors.orange.shade700,
      GpsTrackingStatus.permissionDenied => Colors.red.shade700,
    };
  }

  String _formatTimestamp(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inSeconds < 60) {
      return '${diff.inSeconds}s ago';
    } else if (diff.inMinutes < 60) {
      return '${diff.inMinutes}m ago';
    }
    return '${dt.hour.toString().padLeft(2, '0')}:'
        '${dt.minute.toString().padLeft(2, '0')}:'
        '${dt.second.toString().padLeft(2, '0')}';
  }
}

/// Colored chip showing the GPS tracking status.
class _StatusChip extends StatelessWidget {
  final GpsTrackingStatus status;

  const _StatusChip({required this.status});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (status) {
      GpsTrackingStatus.active => ('Active', Colors.green),
      GpsTrackingStatus.stopped => ('Stopped', Colors.grey),
      GpsTrackingStatus.stale => ('Stale', Colors.orange),
      GpsTrackingStatus.permissionDenied => ('Denied', Colors.red),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.shade300),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.bold,
          color: color.shade800,
        ),
      ),
    );
  }
}

/// Alert banner shown when GPS location is stale or permissions are denied.
class _StaleAlert extends StatelessWidget {
  final GpsTrackingStatus status;

  const _StaleAlert({required this.status});

  @override
  Widget build(BuildContext context) {
    final isPermission = status == GpsTrackingStatus.permissionDenied;
    final color = isPermission ? Colors.red : Colors.orange;
    final message = isPermission
        ? 'Location permission denied. Please enable location services '
            'in your device settings to allow GPS tracking.'
        : 'Location data is stale — no GPS update received for over '
            '30 seconds. Please check that location services are enabled '
            'and the app has background location permission.';
    final icon = isPermission ? Icons.location_disabled : Icons.warning_amber;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.shade300),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 22, color: color.shade700),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                fontSize: 13,
                color: color.shade900,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Simple label-value row.
class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade600,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }
}
