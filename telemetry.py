import time, threading
from typing import Dict, Any, Optional
from pymavlink import mavutil

# 🔐 Verrou global d'E/S MAVLink, exporté pour éventuel partage
MAVLINK_IO_LOCK = threading.RLock()

class TelemetryCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_heartbeat = None
        self._last_global_position = None
        self._last_battery = None
        self._ts: Dict[str, float] = {}

    def update_from_msg(self, msg) -> None:
        with self._lock:
            now = time.time()
            t = msg.get_type()
            self._ts[t] = now
            if t == "HEARTBEAT":
                self._last_heartbeat = msg
            elif t == "GLOBAL_POSITION_INT":
                self._last_global_position = msg
            elif t == "BATTERY_STATUS":
                self._last_battery = msg

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "heartbeat": self._last_heartbeat,
                "global_position": self._last_global_position,
                "battery": self._last_battery,
                "ts": dict(self._ts),
            }

def telemetry_reader(master, cache: TelemetryCache, stop_event: threading.Event) -> None:
    # Demande un flux de télémétrie (protégé par le verrou pour ne pas chevaucher une autre session)
    try:
        with MAVLINK_IO_LOCK:
            master.mav.request_data_stream_send(
                master.target_system, master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL, 2, 1
            )
    except Exception:
        pass

    # Types "mission" à éviter d'avaler côté télémétrie
    MISSION_TYPES = {
        "MISSION_COUNT", "MISSION_REQUEST", "MISSION_REQUEST_INT",
        "MISSION_ITEM", "MISSION_ITEM_INT", "MISSION_ACK",
        "MISSION_CLEAR_ALL", "MISSION_SET_CURRENT"
    }

    while not stop_event.is_set():
        try:
            # On ne garde le verrou que pendant la lecture, pour le relâcher vite
            with MAVLINK_IO_LOCK:
                msg = master.recv_match(blocking=True, timeout=0.5)
            if msg is None:
                continue

            t = msg.get_type()
            # Ne PAS consommer la mission côté cache (on ignore juste ces messages)
            if t in MISSION_TYPES:
                continue

            cache.update_from_msg(msg)
        except Exception:
            continue

GLOBAL_CACHE = TelemetryCache()
_STOP_EVENT = threading.Event()
_READER_THREAD: Optional[threading.Thread] = None

def start_telemetry_reader(master) -> None:
    global _READER_THREAD
    if _READER_THREAD and _READER_THREAD.is_alive():
        return
    _READER_THREAD = threading.Thread(
        target=telemetry_reader, args=(master, GLOBAL_CACHE, _STOP_EVENT), daemon=True
    )
    _READER_THREAD.start()
