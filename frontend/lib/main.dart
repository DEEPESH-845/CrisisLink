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
import 'screens/operator_dashboard_screen.dart';
import 'services/audit_service.dart';
import 'services/dispatch_api_service.dart';
import 'services/firebase_service.dart';

/// Backend base URL — replace with actual Cloud Run URL in production.
const String _backendBaseUrl = 'https://crisislink-api.run.app';

/// Placeholder operator ID — in production, sourced from Firebase Auth.
const String _operatorId = 'operator_001';

/// Placeholder token provider — in production, returns Firebase Auth ID token.
String _tokenProvider() => 'placeholder_token';

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

    return MultiProvider(
      providers: [
        // Firebase service — available via context.read<FirebaseService>().
        Provider<FirebaseService>.value(value: firebaseService),

        // Dispatch API service.
        Provider<DispatchApiService>.value(value: dispatchApiService),

        // Audit service.
        Provider<AuditService>.value(value: auditService),

        // Call state provider — manages all active call streams.
        ChangeNotifierProvider<CallProvider>(
          create: (_) => CallProvider(firebaseService: firebaseService),
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
        home: OperatorDashboardScreen(
          dispatchApiService: dispatchApiService,
          auditService: auditService,
          operatorId: _operatorId,
        ),
      ),
    );
  }
}
