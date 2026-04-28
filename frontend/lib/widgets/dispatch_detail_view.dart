/// Dispatch detail view with Google Maps navigation and case context.
///
/// Displays:
/// - Google Maps with turn-by-turn navigation to caller location
/// - Emergency type and severity
/// - Caller state summary
/// - Key extracted facts from the Intelligence Engine
///
/// Requirements: 7.2, 7.3
library;

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:provider/provider.dart';

import '../models/emergency_classification.dart';
import '../providers/responder_provider.dart';
import '../services/responder_firebase_service.dart';

/// Displays the full dispatch detail: map navigation and case context.
class DispatchDetailView extends StatefulWidget {
  const DispatchDetailView({super.key});

  @override
  State<DispatchDetailView> createState() => _DispatchDetailViewState();
}

class _DispatchDetailViewState extends State<DispatchDetailView> {
  GoogleMapController? _mapController;

  @override
  void dispose() {
    _mapController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<ResponderProvider>(
      builder: (context, provider, _) {
        final dispatch = provider.dispatchDetails;
        if (dispatch == null) {
          return const _NoDispatch();
        }

        final callerLatLng = LatLng(dispatch.callerLat, dispatch.callerLng);

        return Column(
          children: [
            // Google Maps navigation panel
            _MapPanel(
              callerLatLng: callerLatLng,
              onMapCreated: (controller) => _mapController = controller,
            ),

            // Case context card
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _EmergencyHeader(dispatch: dispatch),
                    const SizedBox(height: 12),
                    if (provider.classification != null)
                      _CaseContextCard(
                        classification: provider.classification!,
                      ),
                    if (dispatch.keyFacts.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      _KeyFactsCard(keyFacts: dispatch.keyFacts),
                    ],
                    if (dispatch.callerStateSummary != null) ...[
                      const SizedBox(height: 12),
                      _CallerStateSummaryCard(
                        summary: dispatch.callerStateSummary!,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

/// Google Maps panel showing the caller location with a marker.
class _MapPanel extends StatelessWidget {
  final LatLng callerLatLng;
  final void Function(GoogleMapController) onMapCreated;

  const _MapPanel({
    required this.callerLatLng,
    required this.onMapCreated,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 250,
      child: GoogleMap(
        onMapCreated: onMapCreated,
        initialCameraPosition: CameraPosition(
          target: callerLatLng,
          zoom: 14.0,
        ),
        markers: {
          Marker(
            markerId: const MarkerId('caller_location'),
            position: callerLatLng,
            infoWindow: const InfoWindow(title: 'Caller Location'),
            icon: BitmapDescriptor.defaultMarkerWithHue(
              BitmapDescriptor.hueRed,
            ),
          ),
        },
        myLocationEnabled: true,
        myLocationButtonEnabled: true,
        mapToolbarEnabled: true,
        zoomControlsEnabled: true,
      ),
    );
  }
}

/// Emergency type and severity header with color-coded severity badge.
class _EmergencyHeader extends StatelessWidget {
  final DispatchDetails dispatch;

  const _EmergencyHeader({required this.dispatch});

  @override
  Widget build(BuildContext context) {
    final severityColor = _severityColor(dispatch.severity);

    return Card(
      elevation: 3,
      color: severityColor.withValues(alpha: 0.1),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(
              _emergencyIcon(dispatch.emergencyType),
              size: 36,
              color: severityColor,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    dispatch.emergencyType,
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Call: ${dispatch.callId}',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: severityColor,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                dispatch.severity,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _severityColor(String severity) {
    return switch (severity) {
      'CRITICAL' => Colors.red.shade700,
      'HIGH' => Colors.orange.shade700,
      'MODERATE' => Colors.amber.shade700,
      'LOW' => Colors.green.shade700,
      _ => Colors.grey,
    };
  }

  IconData _emergencyIcon(String type) {
    return switch (type) {
      'MEDICAL' => Icons.local_hospital,
      'FIRE' => Icons.local_fire_department,
      'CRIME' => Icons.shield,
      'ACCIDENT' => Icons.car_crash,
      'DISASTER' => Icons.warning_amber,
      _ => Icons.emergency,
    };
  }
}

/// Case context card showing classification details.
class _CaseContextCard extends StatelessWidget {
  final EmergencyClassification classification;

  const _CaseContextCard({required this.classification});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Case Context',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const Divider(height: 20),
            _InfoRow(
              label: 'Emergency Type',
              value: classification.emergencyType.value,
            ),
            _InfoRow(
              label: 'Severity',
              value: classification.severity.value,
            ),
            _InfoRow(
              label: 'Panic Level',
              value: classification.callerState.panicLevel.value,
            ),
            _InfoRow(
              label: 'Caller Role',
              value: classification.callerState.callerRole.value,
            ),
            _InfoRow(
              label: 'Language',
              value: classification.languageDetected,
            ),
            _InfoRow(
              label: 'Confidence',
              value: '${(classification.confidence * 100).toStringAsFixed(0)}%',
            ),
            if (classification.keyFacts.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Key Facts',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
              const SizedBox(height: 4),
              ...classification.keyFacts.map(
                (fact) => Padding(
                  padding: const EdgeInsets.only(left: 8, bottom: 2),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('• ', style: TextStyle(fontSize: 14)),
                      Expanded(
                        child: Text(fact, style: const TextStyle(fontSize: 14)),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Key facts card.
class _KeyFactsCard extends StatelessWidget {
  final List<String> keyFacts;

  const _KeyFactsCard({required this.keyFacts});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.fact_check,
                    color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Key Facts',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const Divider(height: 20),
            ...keyFacts.map(
              (fact) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.arrow_right,
                        size: 20, color: Colors.grey.shade600),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(fact, style: const TextStyle(fontSize: 14)),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Caller state summary card.
class _CallerStateSummaryCard extends StatelessWidget {
  final String summary;

  const _CallerStateSummaryCard({required this.summary});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      color: Colors.blue.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(Icons.person, color: Colors.blue.shade700),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Caller State',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(summary, style: const TextStyle(fontSize: 14)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Simple label-value row for case context.
class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          SizedBox(
            width: 130,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

/// Placeholder when no dispatch is active.
class _NoDispatch extends StatelessWidget {
  const _NoDispatch();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.directions_car, size: 64, color: Colors.grey.shade300),
          const SizedBox(height: 16),
          Text(
            'No active dispatch',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.grey.shade500,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Waiting for dispatch assignment…',
            style: TextStyle(color: Colors.grey.shade400),
          ),
        ],
      ),
    );
  }
}
