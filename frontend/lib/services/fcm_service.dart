/// Firebase Cloud Messaging service for the Responder App.
///
/// Handles FCM token registration, foreground/background notification
/// listeners, and dispatch push notification display.
///
/// Push notifications contain:
/// - Emergency type
/// - Severity
/// - Estimated caller location
///
/// Requirements: 7.1, 7.3
library;

import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

/// Parsed dispatch notification payload from FCM.
class DispatchNotification {
  final String callId;
  final String emergencyType;
  final String severity;
  final double callerLat;
  final double callerLng;

  const DispatchNotification({
    required this.callId,
    required this.emergencyType,
    required this.severity,
    required this.callerLat,
    required this.callerLng,
  });

  factory DispatchNotification.fromData(Map<String, dynamic> data) {
    return DispatchNotification(
      callId: data['call_id'] as String? ?? '',
      emergencyType: data['emergency_type'] as String? ?? 'UNKNOWN',
      severity: data['severity'] as String? ?? 'LOW',
      callerLat: double.tryParse(data['caller_lat']?.toString() ?? '') ?? 0.0,
      callerLng: double.tryParse(data['caller_lng']?.toString() ?? '') ?? 0.0,
    );
  }
}

/// Service managing Firebase Cloud Messaging for dispatch notifications.
class FcmService {
  final FirebaseMessaging _messaging;

  /// Stream controller for dispatch notifications received while the app
  /// is in the foreground.
  final StreamController<DispatchNotification> _notificationController =
      StreamController<DispatchNotification>.broadcast();

  /// Stream of dispatch notifications for the Responder App to react to.
  Stream<DispatchNotification> get onDispatchNotification =>
      _notificationController.stream;

  /// The current FCM token for this device.
  String? _fcmToken;
  String? get fcmToken => _fcmToken;

  FcmService({FirebaseMessaging? messaging})
      : _messaging = messaging ?? FirebaseMessaging.instance;

  /// Initialize FCM: request permissions, retrieve token, and set up
  /// foreground message listeners.
  ///
  /// Call this once during app startup.
  Future<void> initialize() async {
    // Request notification permissions (required on iOS and Android 13+).
    final settings = await _messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );

    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      debugPrint('FCM: Notification permissions denied by user.');
      return;
    }

    // Retrieve the FCM registration token.
    _fcmToken = await _messaging.getToken();
    debugPrint('FCM token: $_fcmToken');

    // Listen for token refresh.
    _messaging.onTokenRefresh.listen((newToken) {
      _fcmToken = newToken;
      debugPrint('FCM token refreshed: $newToken');
    });

    // Configure foreground notification presentation (iOS).
    await _messaging.setForegroundNotificationPresentationOptions(
      alert: true,
      badge: true,
      sound: true,
    );

    // Listen for foreground messages.
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

    // Listen for notification taps when the app is in background.
    FirebaseMessaging.onMessageOpenedApp.listen(_handleNotificationTap);

    // Check if the app was opened from a terminated state via notification.
    final initialMessage = await _messaging.getInitialMessage();
    if (initialMessage != null) {
      _handleNotificationTap(initialMessage);
    }
  }

  /// Handle a foreground FCM message.
  ///
  /// Parses the dispatch data payload and emits it on the notification stream.
  void _handleForegroundMessage(RemoteMessage message) {
    debugPrint('FCM foreground message: ${message.messageId}');

    final data = message.data;
    if (data.containsKey('call_id')) {
      final notification = DispatchNotification.fromData(
        data.map((k, v) => MapEntry(k, v)),
      );
      _notificationController.add(notification);
    }
  }

  /// Handle a notification tap (app was in background or terminated).
  void _handleNotificationTap(RemoteMessage message) {
    debugPrint('FCM notification tap: ${message.messageId}');

    final data = message.data;
    if (data.containsKey('call_id')) {
      final notification = DispatchNotification.fromData(
        data.map((k, v) => MapEntry(k, v)),
      );
      _notificationController.add(notification);
    }
  }

  /// Subscribe this device to the unit-specific FCM topic.
  ///
  /// The backend sends dispatch notifications to `/topics/unit_{unitId}`.
  Future<void> subscribeToUnit(String unitId) async {
    await _messaging.subscribeToTopic('unit_$unitId');
    debugPrint('FCM: Subscribed to topic unit_$unitId');
  }

  /// Unsubscribe from the unit-specific FCM topic.
  Future<void> unsubscribeFromUnit(String unitId) async {
    await _messaging.unsubscribeFromTopic('unit_$unitId');
    debugPrint('FCM: Unsubscribed from topic unit_$unitId');
  }

  /// Clean up resources.
  void dispose() {
    _notificationController.close();
  }
}
