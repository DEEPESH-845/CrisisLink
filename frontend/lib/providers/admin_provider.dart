/// ChangeNotifier managing Admin Dashboard state.
///
/// Subscribes to Firebase RTDB streams for live unit and incident data,
/// and fetches analytics from the backend BigQuery/Vertex AI endpoints.
///
/// Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/response_unit.dart';
import '../services/admin_firebase_service.dart';
import '../services/analytics_service.dart';

/// Central state manager for the Admin Dashboard.
class AdminProvider extends ChangeNotifier {
  final AdminFirebaseService _firebaseService;
  final AnalyticsService _analyticsService;

  AdminProvider({
    required AdminFirebaseService firebaseService,
    required AnalyticsService analyticsService,
  })  : _firebaseService = firebaseService,
        _analyticsService = analyticsService;

  // ---------------------------------------------------------------------------
  // State fields
  // ---------------------------------------------------------------------------

  /// Live list of all Response_Units.
  List<ResponseUnit> _units = [];

  /// Live list of incident summaries for the heatmap.
  List<IncidentSummary> _incidents = [];

  /// Whether connected to Firebase RTDB.
  bool _isConnected = true;

  /// Response time analytics by region.
  List<ResponseTimeEntry> _responseTimesByRegion = [];

  /// Response time analytics by time of day.
  List<ResponseTimeEntry> _responseTimesByTimeOfDay = [];

  /// Response time analytics by emergency type.
  List<ResponseTimeEntry> _responseTimesByEmergencyType = [];

  /// Classification accuracy metrics.
  ClassificationAccuracyMetrics _classificationAccuracy =
      const ClassificationAccuracyMetrics(
    totalClassifications: 0,
    operatorOverrides: 0,
    falseClassificationRate: 0.0,
  );

  /// Vertex AI trend reports.
  List<TrendReportEntry> _trendReports = [];

  /// Whether analytics data is currently loading.
  bool _isLoadingAnalytics = false;

  /// Error message from the last analytics fetch, if any.
  String? _analyticsError;

  // ---------------------------------------------------------------------------
  // Stream subscriptions
  // ---------------------------------------------------------------------------

  final List<StreamSubscription<dynamic>> _subscriptions = [];

  // ---------------------------------------------------------------------------
  // Getters
  // ---------------------------------------------------------------------------

  List<ResponseUnit> get units => List.unmodifiable(_units);
  List<IncidentSummary> get incidents => List.unmodifiable(_incidents);
  bool get isConnected => _isConnected;

  List<ResponseTimeEntry> get responseTimesByRegion =>
      List.unmodifiable(_responseTimesByRegion);
  List<ResponseTimeEntry> get responseTimesByTimeOfDay =>
      List.unmodifiable(_responseTimesByTimeOfDay);
  List<ResponseTimeEntry> get responseTimesByEmergencyType =>
      List.unmodifiable(_responseTimesByEmergencyType);

  ClassificationAccuracyMetrics get classificationAccuracy =>
      _classificationAccuracy;
  List<TrendReportEntry> get trendReports =>
      List.unmodifiable(_trendReports);

  bool get isLoadingAnalytics => _isLoadingAnalytics;
  String? get analyticsError => _analyticsError;

  // ---------------------------------------------------------------------------
  // Derived getters
  // ---------------------------------------------------------------------------

  /// Count of units by status.
  Map<UnitStatus, int> get unitStatusCounts {
    final counts = <UnitStatus, int>{};
    for (final unit in _units) {
      counts[unit.status] = (counts[unit.status] ?? 0) + 1;
    }
    return counts;
  }

  /// Count of active incidents (status == active or dispatched).
  int get activeIncidentCount =>
      _incidents.where((i) => i.isActive).length;

  /// Count of available units.
  int get availableUnitCount =>
      _units.where((u) => u.status == UnitStatus.available).length;

  // ---------------------------------------------------------------------------
  // Subscription management
  // ---------------------------------------------------------------------------

  /// Start listening to Firebase RTDB streams for live data.
  void startListening() {
    _cancelSubscriptions();

    // Connection state.
    _subscriptions.add(
      _firebaseService.connectionState.listen(
        (connected) {
          _isConnected = connected;
          notifyListeners();
        },
        onError: (_) {
          _isConnected = false;
          notifyListeners();
        },
      ),
    );

    // All units stream.
    _subscriptions.add(
      _firebaseService.allUnitsStream().listen(
        (units) {
          _units = units;
          notifyListeners();
        },
        onError: (_) {
          // Keep existing data on error.
        },
      ),
    );

    // Incidents stream.
    _subscriptions.add(
      _firebaseService.incidentsStream().listen(
        (incidents) {
          _incidents = incidents;
          notifyListeners();
        },
        onError: (_) {
          // Keep existing data on error.
        },
      ),
    );
  }

  /// Cancel all active subscriptions.
  void _cancelSubscriptions() {
    for (final sub in _subscriptions) {
      sub.cancel();
    }
    _subscriptions.clear();
  }

  // ---------------------------------------------------------------------------
  // Analytics data fetching
  // ---------------------------------------------------------------------------

  /// Fetch all analytics data from the backend (BigQuery + Vertex AI).
  ///
  /// Fetches response times (by region, time of day, emergency type),
  /// classification accuracy, and trend reports in parallel.
  Future<void> fetchAnalytics() async {
    _isLoadingAnalytics = true;
    _analyticsError = null;
    notifyListeners();

    try {
      final results = await Future.wait([
        _analyticsService.fetchResponseTimes(breakdownType: 'region'),
        _analyticsService.fetchResponseTimes(breakdownType: 'time_of_day'),
        _analyticsService.fetchResponseTimes(
            breakdownType: 'emergency_type'),
        _analyticsService.fetchClassificationAccuracy(),
        _analyticsService.fetchTrendReports(),
      ]);

      _responseTimesByRegion = results[0] as List<ResponseTimeEntry>;
      _responseTimesByTimeOfDay = results[1] as List<ResponseTimeEntry>;
      _responseTimesByEmergencyType = results[2] as List<ResponseTimeEntry>;
      _classificationAccuracy =
          results[3] as ClassificationAccuracyMetrics;
      _trendReports = results[4] as List<TrendReportEntry>;
    } catch (e) {
      _analyticsError = 'Failed to load analytics: $e';
    } finally {
      _isLoadingAnalytics = false;
      notifyListeners();
    }
  }

  /// Refresh analytics data (convenience wrapper).
  Future<void> refreshAnalytics() => fetchAnalytics();

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  @override
  void dispose() {
    _cancelSubscriptions();
    super.dispose();
  }
}
