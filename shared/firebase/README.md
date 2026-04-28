# CrisisLink Firebase Configuration

Firebase project configuration for CrisisLink Emergency AI Co-Pilot.

## Structure

- `firebase.json` — Firebase project configuration (hosting, database, emulators)
- `.firebaserc` — Firebase project aliases (prod, staging)
- `database.rules.json` — Firebase Realtime DB security rules with RBAC

## Roles

The security rules enforce role-based access control (RBAC) via custom auth claims:

| Role | Access |
|------|--------|
| `operator` | Read call data, write dispatch confirmations and overrides |
| `responder` | Read own unit data and dispatch details, write own status/location |
| `admin` | Read all data, manage unit configuration |
| `service` | Backend service accounts — write call data, classifications, dispatch cards |

## Local Development

```bash
firebase emulators:start
```

The database emulator runs on port 9000 and the hosting emulator on port 5000.
