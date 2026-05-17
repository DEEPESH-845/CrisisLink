"""Seed Firebase RTDB with demo response units near Chandigarh.

Run from backend/ after configuring GOOGLE_APPLICATION_CREDENTIALS
and FIREBASE_DATABASE_URL in .env.

Usage:
    cd backend
    python3 seed_firebase.py
"""
import os
import time

from dotenv import load_dotenv

load_dotenv()

UNITS = {
    "AMB_007": {
        "type": "AMBULANCE",
        "status": "available",
        "location": {"lat": 30.7340, "lng": 76.7820},
        "capabilities": ["CARDIAC", "TRAUMA"],
        "hospital_or_station": "PGIMER Chandigarh",
        "last_updated": int(time.time()),
    },
    "AMB_012": {
        "type": "AMBULANCE",
        "status": "available",
        "location": {"lat": 30.7290, "lng": 76.7750},
        "capabilities": ["GENERAL"],
        "hospital_or_station": "GMC Sector 32",
        "last_updated": int(time.time()),
    },
    "AMB_019": {
        "type": "AMBULANCE",
        "status": "available",
        "location": {"lat": 30.7380, "lng": 76.7700},
        "capabilities": ["PEDIATRIC", "TRAUMA"],
        "hospital_or_station": "GMSH Sector 16",
        "last_updated": int(time.time()),
    },
    "FIRE_003": {
        "type": "FIRE_BRIGADE",
        "status": "available",
        "location": {"lat": 30.7400, "lng": 76.7900},
        "capabilities": ["FIRE_RESCUE"],
        "hospital_or_station": "Fire Station Sector 17",
        "last_updated": int(time.time()),
    },
    "POL_021": {
        "type": "POLICE",
        "status": "available",
        "location": {"lat": 30.7310, "lng": 76.7800},
        "capabilities": ["GENERAL"],
        "hospital_or_station": "Police Station Sector 11",
        "last_updated": int(time.time()),
    },
}


def main() -> None:
    firebase_url = os.environ.get("FIREBASE_DATABASE_URL", "")
    if not firebase_url or "your-project" in firebase_url:
        print("❌ FIREBASE_DATABASE_URL is not configured in .env")
        print("   Set it to your real Firebase RTDB URL and try again.")
        return

    try:
        import firebase_admin
        from firebase_admin import credentials, db
    except ImportError:
        print("❌ firebase-admin is not installed. Run: pip3 install firebase-admin")
        return

    try:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not firebase_admin._apps:
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            else:
                cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {"databaseURL": firebase_url})
    except Exception as exc:
        print(f"❌ Firebase initialization failed: {exc}")
        return

    ref = db.reference("units")
    for unit_id, data in UNITS.items():
        ref.child(unit_id).set(data)
        print(f"  ✅ Written: {unit_id} ({data['type']}) at {data['hospital_or_station']}")

    print(f"\n✅ Seeded {len(UNITS)} units to Firebase RTDB at /units/")
    print(f"   View at: {firebase_url}/units.json")


if __name__ == "__main__":
    main()
