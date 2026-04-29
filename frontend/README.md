# CrisisLink Frontend

Flutter unified app for the **CrisisLink Emergency AI Co-Pilot**, serving three user roles — Operators, Field Responders, and Admins — from a single codebase. Built with Flutter Web and Firebase real-time streams.

---

## Screens

| Screen | Role | Description |
|---|---|---|
| **Operator Dashboard** | 911 Operator | Live AI triage card, streaming transcript, one-tap dispatch, caller guidance status |
| **Responder Screen** | Field Responder | Dispatch notifications, GPS navigation, status transitions |
| **Admin Dashboard** | PSAP Admin | Response time analytics, incident heatmaps, unit availability, trend reports |

---

## Prerequisites

- **Flutter SDK 3.2.0+** (Dart SDK included)
- **Chrome** (for Flutter Web development)
- **Firebase project** with Realtime Database, Authentication, and Cloud Messaging enabled
- **Google Maps API key** (for the responder map view)

---

## Local Setup

### 1. Install Flutter

Follow the official guide for your OS: [https://docs.flutter.dev/get-started/install](https://docs.flutter.dev/get-started/install)

Verify your installation:

```bash
flutter doctor
```

Make sure Flutter Web is enabled:

```bash
flutter config --enable-web
```

### 2. Clone the repository

```bash
git clone https://github.com/<your-org>/crisislink.git
cd crisislink/frontend
```

### 3. Install dependencies

```bash
flutter pub get
```

### 4. Configure Firebase

The app uses Firebase for real-time data, authentication, and push notifications. You need to connect it to your Firebase project.

#### Option A: Using FlutterFire CLI (recommended)

```bash
# Install the FlutterFire CLI
dart pub global activate flutterfire_cli

# Configure Firebase (generates firebase_options.dart)
flutterfire configure --project=<your-firebase-project-id>
```

#### Option B: Manual configuration

1. Go to [Firebase Console](https://console.firebase.google.com/) → Project Settings
2. Add a **Web app** to your Firebase project
3. Copy the config values into `lib/firebase_options.dart`, replacing the placeholder values:

```dart
static const FirebaseOptions web = FirebaseOptions(
  apiKey: 'YOUR_ACTUAL_API_KEY',
  appId: 'YOUR_ACTUAL_APP_ID',
  messagingSenderId: 'YOUR_SENDER_ID',
  projectId: 'your-project-id',
  databaseURL: 'https://your-project-default-rtdb.firebaseio.com',
  storageBucket: 'your-project.appspot.com',
);
```

Repeat for Android and iOS if targeting those platforms.

### 5. Configure the backend URL

In `lib/main.dart`, update the backend base URL to point to your local or deployed backend:

```dart
// For local development (backend running on your machine)
const String _backendBaseUrl = 'http://localhost:8001';

// For production (Cloud Run deployment)
const String _backendBaseUrl = 'https://crisislink-api.run.app';
```

### 6. Set up Google Maps (for Responder screen)

1. Enable the **Maps JavaScript API** in your [Google Cloud Console](https://console.cloud.google.com/apis/library)
2. Add your API key to `web/index.html`:

```html
<head>
  <!-- Add this before the closing </head> tag -->
  <script src="https://maps.googleapis.com/maps/api/js?key=YOUR_MAPS_API_KEY"></script>
</head>
```

---

## Running the App

### Flutter Web (primary target)

```bash
flutter run -d chrome
```

### Flutter Web with a specific port

```bash
flutter run -d chrome --web-port=8080
```

### Build for production

```bash
flutter build web
```

The build output will be in `build/web/` — deploy this to Firebase Hosting, Cloud Run, or any static host.

---

## Testing

```bash
# Run all tests
flutter test

# Run a specific test file
flutter test test/some_test.dart

# Run with verbose output
flutter test --reporter expanded
```

The project uses `fast_check` for property-based testing alongside standard `flutter_test`.

---

## Project Structure

```
frontend/
├── lib/
│   ├── main.dart                    # App entry point, Provider wiring, routing
│   ├── firebase_options.dart        # Firebase config (generated or manual)
│   ├── models/                      # Data models
│   │   ├── call_session.dart        # Active call session
│   │   ├── dispatch_card.dart       # Dispatch recommendation card
│   │   ├── emergency_classification.dart  # AI classification result
│   │   └── response_unit.dart       # Field response unit
│   ├── providers/                   # State management (Provider)
│   │   ├── call_provider.dart       # Active call streams & state
│   │   ├── responder_provider.dart  # Responder location & status
│   │   └── admin_provider.dart      # Admin analytics state
│   ├── screens/                     # Full-page screens
│   │   ├── operator_dashboard_screen.dart  # Operator view
│   │   ├── responder_screen.dart           # Field responder view
│   │   └── admin_dashboard_screen.dart     # Admin analytics view
│   ├── services/                    # Backend & Firebase communication
│   │   ├── firebase_service.dart           # Firebase RTDB streams
│   │   ├── dispatch_api_service.dart       # Dispatch API client
│   │   ├── audit_service.dart              # Audit logging client
│   │   ├── analytics_service.dart          # Analytics data fetching
│   │   ├── fcm_service.dart                # Push notification handling
│   │   ├── gps_service.dart                # GPS location tracking
│   │   ├── admin_firebase_service.dart     # Admin-specific Firebase queries
│   │   └── responder_firebase_service.dart # Responder-specific Firebase queries
│   └── widgets/                     # Reusable UI components
│       ├── triage_card.dart                # AI triage classification card
│       ├── dispatch_card_widget.dart       # Ranked dispatch recommendations
│       ├── dispatch_detail_view.dart       # Dispatch detail overlay
│       ├── guidance_status.dart            # Caller guidance status indicator
│       ├── classification_accuracy.dart    # AI confidence display
│       ├── classification_override.dart    # Operator override controls
│       ├── connection_banner.dart          # Network connectivity banner
│       ├── error_notification.dart         # Error/subsystem failure alerts
│       ├── timeout_alert.dart              # AI response timeout warning
│       ├── gps_status_indicator.dart       # GPS signal status
│       ├── status_transition_buttons.dart  # Unit status controls
│       ├── incident_heatmap.dart           # Admin: incident density map
│       ├── response_time_analytics.dart    # Admin: response time charts
│       ├── trend_reports.dart              # Admin: trend analysis
│       └── unit_availability_overview.dart # Admin: unit status overview
├── web/
│   ├── index.html           # Web entry point
│   └── manifest.json        # PWA manifest
├── pubspec.yaml             # Flutter dependencies
└── analysis_options.yaml    # Dart linter rules
```

---

## Key Dependencies

| Package | Purpose |
|---|---|
| `firebase_core` | Firebase initialization |
| `firebase_database` | Realtime Database streams (live triage, dispatch, transcripts) |
| `firebase_auth` | User authentication (operator, responder, admin roles) |
| `firebase_messaging` | Push notifications for dispatch alerts |
| `google_maps_flutter` | Map view for responder navigation |
| `provider` | State management |
| `http` | REST API calls to backend services |
| `fast_check` | Property-based testing |

---

## State Management

The app uses **Provider** for state management. Key providers:

- **CallProvider** — Listens to Firebase RTDB streams for active calls, manages transcript and classification state for the operator dashboard.
- **ResponderProvider** — Tracks the responder's GPS location, dispatch assignments, and status transitions.
- **AdminProvider** — Fetches and caches analytics data for the admin dashboard.

All Firebase streams are set up in the providers, so UI widgets rebuild automatically when data changes.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `flutter pub get` fails | Make sure your Flutter SDK is 3.2.0+. Run `flutter upgrade` if needed |
| Firebase errors on launch | Verify `firebase_options.dart` has real project values, not placeholders |
| Blank screen on Chrome | Check the browser console for errors. Usually a missing Firebase config |
| Google Maps not loading | Ensure the Maps JavaScript API is enabled and the key is in `web/index.html` |
| CORS errors calling backend | Run the backend with CORS middleware enabled, or use a proxy in development |
| Push notifications not working | FCM requires HTTPS. Use `flutter run -d chrome --web-port=8080` and access via localhost |
