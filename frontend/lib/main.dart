/// CrisisLink Emergency AI Co-Pilot — Flutter unified app.
///
/// Wires up Provider state management, Firebase services, and routes
/// to the Operator Dashboard.
///
/// Requirements: 6.1
library;

import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:provider/provider.dart';

import 'firebase_options.dart';
import 'providers/call_provider.dart';
import 'providers/responder_provider.dart';
import 'screens/admin_dashboard_screen.dart';
import 'screens/operator_dashboard_screen.dart';
import 'screens/responder_screen.dart';
import 'services/admin_firebase_service.dart';
import 'services/audit_service.dart';
import 'services/analytics_service.dart';
import 'services/dispatch_api_service.dart';
import 'services/firebase_service.dart';
import 'services/fcm_service.dart';
import 'services/gps_service.dart';
import 'services/responder_firebase_service.dart';

/// Backend base URL. Override with:
/// `flutter run --dart-define=CRISISLINK_BACKEND_URL=http://localhost:8003`
const String _backendBaseUrl = String.fromEnvironment(
  'CRISISLINK_BACKEND_URL',
  defaultValue: 'http://localhost:8003',
);

/// Placeholder operator ID — in production, sourced from Firebase Auth.
const String _operatorId = 'operator_001';

/// Demo token provider. Replace with Firebase Auth ID token in production.
String _tokenProvider() => const String.fromEnvironment(
      'CRISISLINK_API_TOKEN',
      defaultValue: 'crisislink-dev-token',
    );

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const CrisisLinkApp());
}

class CrisisLinkApp extends StatelessWidget {
  const CrisisLinkApp({super.key});

  @override
  Widget build(BuildContext context) {
    // Create service instances.
    final firebaseService = FirebaseService();
    final dispatchApiService = DispatchApiService(
      baseUrl: _backendBaseUrl,
      tokenProvider: _tokenProvider,
    );
    final auditService = AuditService(
      baseUrl: _backendBaseUrl,
      tokenProvider: _tokenProvider,
    );
    final adminFirebaseService = AdminFirebaseService();
    final analyticsService = AnalyticsService(
      baseUrl: _backendBaseUrl,
      tokenProvider: _tokenProvider,
    );
    final responderFirebaseService = ResponderFirebaseService();
    final fcmService = FcmService();
    final gpsService = GpsService(
      firebaseService: responderFirebaseService,
      positionProvider: () async => const GpsPosition(
        latitude: 30.7333,
        longitude: 76.7794,
      ),
    );

    return MultiProvider(
      providers: [
        // Firebase service — available via context.read<FirebaseService>().
        Provider<FirebaseService>.value(value: firebaseService),

        // Dispatch API service.
        Provider<DispatchApiService>.value(value: dispatchApiService),

        // Audit service.
        Provider<AuditService>.value(value: auditService),

        Provider<AdminFirebaseService>.value(value: adminFirebaseService),
        Provider<AnalyticsService>.value(value: analyticsService),
        Provider<ResponderFirebaseService>.value(value: responderFirebaseService),
        Provider<FcmService>.value(value: fcmService),
        Provider<GpsService>.value(value: gpsService),

        // Call state provider — manages all active call streams.
        ChangeNotifierProvider<CallProvider>(
          create: (_) => CallProvider(firebaseService: firebaseService),
        ),
        ChangeNotifierProvider<ResponderProvider>(
          create: (_) => ResponderProvider(
            firebaseService: responderFirebaseService,
            fcmService: fcmService,
            gpsService: gpsService,
          ),
        ),
      ],
      child: MaterialApp(
        title: 'CrisisLink — Operator Dashboard',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorSchemeSeed: const Color(0xFF1565C0),
          useMaterial3: true,
          brightness: Brightness.light,
        ),
        initialRoute: '/',
        routes: {
          '/': (_) => OperatorDashboardScreen(
                dispatchApiService: dispatchApiService,
                auditService: auditService,
                operatorId: _operatorId,
              ),
          '/responder': (_) => const ResponderScreen(),
          '/admin': (_) => AdminDashboardScreen(
                adminFirebaseService: adminFirebaseService,
                analyticsService: analyticsService,
              ),
        },
      ),
    );
  }
}
