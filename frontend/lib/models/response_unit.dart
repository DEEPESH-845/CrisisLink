/// Dart data models for Response Unit, mirroring backend Pydantic models.
///
/// Requirements: 4.1, 4.6, 7.4, 8.2, 8.4
library;

/// Response unit type.
enum UnitType {
  ambulance('ambulance'),
  fireBrigade('fire_brigade'),
  police('police');

  const UnitType(this.value);
  final String value;

  static UnitType fromString(String s) =>
      UnitType.values.firstWhere(
        (e) => e.value == s,
        orElse: () => UnitType.ambulance,
      );
}

/// Response unit operational status.
enum UnitStatus {
  available('available'),
  dispatched('dispatched'),
  onScene('on_scene'),
  returning('returning');

  const UnitStatus(this.value);
  final String value;

  static UnitStatus fromString(String s) =>
      UnitStatus.values.firstWhere(
        (e) => e.value == s,
        orElse: () => UnitStatus.available,
      );
}

/// GPS coordinates.
class Location {
  final double lat;
  final double lng;

  const Location({required this.lat, required this.lng});

  factory Location.fromJson(Map<String, dynamic> json) {
    return Location(
      lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
      lng: (json['lng'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {'lat': lat, 'lng': lng};
}

/// An emergency response vehicle tracked in Firebase RTDB.
class ResponseUnit {
  final String unitId;
  final UnitType type;
  final UnitStatus status;
  final Location location;
  final String hospitalOrStation;
  final List<String> capabilities;
  final int lastUpdated;

  const ResponseUnit({
    required this.unitId,
    required this.type,
    required this.status,
    required this.location,
    required this.hospitalOrStation,
    required this.capabilities,
    required this.lastUpdated,
  });

  factory ResponseUnit.fromJson(Map<String, dynamic> json) {
    return ResponseUnit(
      unitId: json['unit_id'] as String? ?? '',
      type: UnitType.fromString(json['type'] as String? ?? 'ambulance'),
      status: UnitStatus.fromString(json['status'] as String? ?? 'available'),
      location: json['location'] != null
          ? Location.fromJson(json['location'] as Map<String, dynamic>)
          : const Location(lat: 0, lng: 0),
      hospitalOrStation: json['hospital_or_station'] as String? ?? '',
      capabilities: (json['capabilities'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      lastUpdated: json['last_updated'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'unit_id': unitId,
        'type': type.value,
        'status': status.value,
        'location': location.toJson(),
        'hospital_or_station': hospitalOrStation,
        'capabilities': capabilities,
        'last_updated': lastUpdated,
      };
}
