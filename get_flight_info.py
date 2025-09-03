import math, time
from typing import Dict, Any
import json
from pymavlink import mavutil
from telemetry import TelemetryCache, MAVLINK_IO_LOCK 

# ─────────────────────────────────────────────
# Fonction : build_flight_info
# But : Construire un snapshot d’infos de vol à partir du cache de télémétrie
# Étapes :
#   - Récupère un snapshot (heartbeat, global_position, timestamps)
#   - Vérifie la fraîcheur des données (stale_after)
#   - Calcule vitesses horizontale/verticale et cap
#   - Retourne un dictionnaire normalisé (lat, lon, alt, mode, armé, etc.)
#   - Lève une erreur si données manquantes ou trop anciennes (si allow_stale=False)
# ─────────────────────────────────────────────
def build_flight_info(
    drone_id: str,
    cache: TelemetryCache,
    stale_after: float = 2.0,
    allow_stale: bool = True,
) -> Dict[str, Any]:
    snap = cache.snapshot()
    hb = snap.get("heartbeat")
    gp = snap.get("global_position")
    ts = snap.get("ts", {})
    now = time.time()

    if gp is None or hb is None:
        raise RuntimeError("Aucune donnée de position ou heartbeat reçue.")

    age_pos = now - ts.get("GLOBAL_POSITION_INT", 0)
    age_hb  = now - ts.get("HEARTBEAT", 0)
    is_stale = (age_pos > stale_after) or (age_hb > stale_after)

    if is_stale and not allow_stale:
        raise RuntimeError("Télémétrie trop ancienne ou absente.")

    vx, vy, vz = gp.vx/100.0, gp.vy/100.0, gp.vz/100.0

    return {
        "drone_id": str(drone_id),
        "is_armed": (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0,
        "flight_mode": mavutil.mode_string_v10(hb),
        "latitude": gp.lat / 1e7,
        "longitude": gp.lon / 1e7,
        "altitude_m": gp.relative_alt / 1000.0,
        "horizontal_speed_m_s": round((vx*vx + vy*vy)**0.5, 2),
        "vertical_speed_m_s": round(vz, 2),
        "heading_deg": (gp.hdg / 100.0) if getattr(gp, "hdg", None) is not None else 0.0,
        "movement_track_deg": (gp.hdg / 100.0) if getattr(gp, "hdg", None) is not None else None,
        "battery_remaining_percent": getattr(snap.get("battery"), "battery_remaining", None)
            if snap.get("battery") else None,
        "stale": is_stale,
        "age_sec": {"position": round(age_pos, 3), "heartbeat": round(age_hb, 3)},
    }


# ─────────────────────────────────────────────
# Fonction : flight_info
# But : Lire directement les infos de vol sur le lien MAVLink (sans passer par le cache)
# Étapes :
#   - (Optionnel) Demande de flux MAVLink (request_data_stream_send)
#   - Sous verrou MAVLINK_IO_LOCK : lit HEARTBEAT et GLOBAL_POSITION_INT
#   - Valide la présence des messages requis
#   - Calcule vitesses et extrait cap/position/altitude/mode
#   - Retourne un dictionnaire normalisé (similaire à build_flight_info)
# ─────────────────────────────────────────────
def flight_info(
    drone_id: str,
    master,
    timeout: float = 5.0,
    request_stream: bool = True
) -> Dict[str, Any]:
    """
    Lecture directe sur le lien MAVLink (sans passer par le cache).
    Protégée par MAVLINK_IO_LOCK pour éviter les collisions avec la télémétrie/mission.
    """
    with MAVLINK_IO_LOCK:
        if request_stream:
            try:
                master.mav.request_data_stream_send(
                    master.target_system, master.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL, 2, 1
                )
            except Exception:
                pass

        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=timeout)
        gp = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=timeout)

    if not hb or not gp:
        raise RuntimeError("Aucune donnée de position ou heartbeat reçue.")

    vx, vy, vz = gp.vx/100.0, gp.vy/100.0, gp.vz/100.0

    return {
        "drone_id": str(drone_id),
        "is_armed": (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0,
        "flight_mode": mavutil.mode_string_v10(hb),
        "latitude": gp.lat / 1e7,
        "longitude": gp.lon / 1e7,
        "altitude_m": gp.relative_alt / 1000.0,
        "horizontal_speed_m_s": round((vx*vx + vy*vy)**0.5, 2),
        "vertical_speed_m_s": round(vz, 2),
        "heading_deg": (gp.hdg / 100.0) if getattr(gp, "hdg", None) is not None else 0.0,
        "movement_track_deg": (gp.hdg / 100.0) if getattr(gp, "hdg", None) is not None else None,
        "battery_remaining_percent": None, 
    }
