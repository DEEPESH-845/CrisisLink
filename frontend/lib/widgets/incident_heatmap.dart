/// Live incident heatmap widget for the Admin Dashboard.
///
/// Displays active and recent incidents by geographic location using
/// Google Maps with colored markers indicating emergency type and severity.
///
/// Requirements: 9.1
library;

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:provider/provider.dart';

import '../models/emergency_classification.dart';
import '../providers/admin_provider.dart';
import '../services/admin_firebase_service.dart';

/// Live incident heatmap showing active and recent incidents.
class IncidentHeatmap extends StatefulWidget {
  const IncidentHeatmap({super.key});

  @override
  State<IncidentHeatmap> createState() => _IncidentHeatmapState();
}

class _IncidentHeatmapState extends State<IncidentHeatmap> {
  GoogleMapController? _mapController;

  /// Default center: New Delhi, India.
  static const _defaultCenter = LatLng(28.6139, 77.2090);
  static const _defaultZoom = 10.0;

  @override
  void dispose() {
    _mapController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AdminProvider>(
      builder: (context, provider, _) {
        final incidents = provider.incidents;
        final markers = _buildMarkers(incidents);

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
                    Icon(Icons.map, color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Live Incident Heatmap',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const Spacer(),
                    _IncidentCountBadge(
                      count: provider.activeIncidentCount,
                      label: 'Active',
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),

              // Map
              Expanded(
                child: GoogleMap(
                  initialCameraPosition: const CameraPosition(
                    target: _defaultCenter,
                    zoom: _defaultZoom,
                  ),
                  markers: markers,
                  onMapCreated: (controller) {
                    _mapController = controller;
                  },
                  myLocationEnabled: false,
                  zoomControlsEnabled: true,
                  mapToolbarEnabled: false,
                ),
              ),

              // Legend
              const _HeatmapLegend(),
            ],
          ),
        );
      },
    );
  }

  /// Build map markers from incident summaries.
  Set<Marker> _buildMarkers(List<IncidentSummary> incidents) {
    final markers = <Marker>{};
    for (final incident in incidents) {
      // Skip incidents without valid coordinates.
      if (incident.lat == 0.0 && incident.lng == 0.0) continue;

      markers.add(Marker(
        markerId: MarkerId(incident.callId),
        position: LatLng(incident.lat, incident.lng),
        icon: BitmapDescriptor.defaultMarkerWithHue(
          _markerHue(incident.emergencyType, incident.isActive),
        ),
        infoWindow: InfoWindow(
          title: '${incident.emergencyType.value} — ${incident.severity.value}',
          snippet: incident.isActive ? 'Active' : 'Recent',
        ),
      ));
    }
    return markers;
  }

  /// Map emergency type to marker hue.
  double _markerHue(EmergencyType type, bool isActive) {
    if (!isActive) return BitmapDescriptor.hueYellow;
    switch (type) {
      case EmergencyType.medical:
        return BitmapDescriptor.hueRed;
      case EmergencyType.fire:
        return BitmapDescriptor.hueOrange;
      case EmergencyType.crime:
        return BitmapDescriptor.hueBlue;
      case EmergencyType.accident:
        return BitmapDescriptor.hueMagenta;
      case EmergencyType.disaster:
        return BitmapDescriptor.hueViolet;
      case EmergencyType.unknown:
        return BitmapDescriptor.hueYellow;
    }
  }
}

/// Badge showing the count of active incidents.
class _IncidentCountBadge extends StatelessWidget {
  final int count;
  final String label;

  const _IncidentCountBadge({required this.count, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: count > 0 ? Colors.red.shade100 : Colors.green.shade100,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '$count $label',
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: count > 0 ? Colors.red.shade800 : Colors.green.shade800,
        ),
      ),
    );
  }
}

/// Legend for the heatmap marker colors.
class _HeatmapLegend extends StatelessWidget {
  const _HeatmapLegend();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Wrap(
        spacing: 16,
        runSpacing: 4,
        children: const [
          _LegendItem(color: Colors.red, label: 'Medical'),
          _LegendItem(color: Colors.orange, label: 'Fire'),
          _LegendItem(color: Colors.blue, label: 'Crime'),
          _LegendItem(color: Colors.purple, label: 'Accident'),
          _LegendItem(color: Colors.deepPurple, label: 'Disaster'),
          _LegendItem(color: Colors.amber, label: 'Recent / Unknown'),
        ],
      ),
    );
  }
}

/// Single legend item with a colored dot and label.
class _LegendItem extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendItem({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 12)),
      ],
    );
  }
}
