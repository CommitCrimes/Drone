import time, threading
from typing import Dict, Any, Optional, Hashable
from pymavlink import mavutil

# Verrou I/O MAVLink partagé (évite les collisions avec d'autres threads, ex: missions)
MAVLINK_IO_LOCK = threading.RLock()

# ─────────────────────────────────────────────
# Cache de télémétrie
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# Boucle lecteur
# ─────────────────────────────────────────────
def telemetry_reader(master, cache: TelemetryCache, stop_event: threading.Event) -> None:
    # Demande d'un flux de télémétrie
    try:
        with MAVLINK_IO_LOCK:
            master.mav.request_data_stream_send(
                master.target_system, master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL, 2, 1
            )
    except Exception:
        pass

    # Messages "mission" à ne pas consommer ici
    MISSION_TYPES = {
        "MISSION_COUNT", "MISSION_REQUEST", "MISSION_REQUEST_INT",
        "MISSION_ITEM", "MISSION_ITEM_INT", "MISSION_ACK",
        "MISSION_CLEAR_ALL", "MISSION_SET_CURRENT"
    }

    while not stop_event.is_set():
        try:
            with MAVLINK_IO_LOCK:
                msg = master.recv_match(blocking=True, timeout=0.5)
            if msg is None:
                continue
            if msg.get_type() in MISSION_TYPES:
                continue
            cache.update_from_msg(msg)
        except Exception:
            continue

# ─────────────────────────────────────────────
# Multi-drones: registre de threads/caches par clé
# ─────────────────────────────────────────────
_CACHES: Dict[Hashable, TelemetryCache] = {}
_STOPS: Dict[Hashable, threading.Event] = {}
_THREADS: Dict[Hashable, threading.Thread] = {}

# Rétro-compat (si on appelle sans key/cache)
GLOBAL_CACHE = TelemetryCache()
_LEGACY_KEY: Hashable = "__legacy__"

def start_telemetry_reader(
    master,
    cache: Optional[TelemetryCache] = None,
    key: Optional[Hashable] = None,
) -> TelemetryCache:
    """
    Démarre (ou réutilise) un lecteur de télémétrie pour 'key'.
    - key: identifiant du drone (ex: drone_id). Si None, on utilise un mode legacy global.
    - cache: si None, un TelemetryCache est créé (ou GLOBAL_CACHE en legacy).
    Retourne le cache utilisé.
    """
    # Mode legacy (compat)
    if cache is None and key is None:
        key = _LEGACY_KEY
        cache = GLOBAL_CACHE

    # Clé par défaut si non fournie: identifiant unique du master
    if key is None:
        key = id(master)
    if cache is None:
        cache = TelemetryCache()

    thr = _THREADS.get(key)
    if thr and thr.is_alive():
        # déjà lancé → retourne le cache existant
        return _CACHES[key]

    stop = threading.Event()
    t = threading.Thread(target=telemetry_reader, args=(master, cache, stop), daemon=True)
    _CACHES[key] = cache
    _STOPS[key] = stop
    _THREADS[key] = t
    t.start()
    return cache

def stop_telemetry_reader(key: Hashable) -> None:
    """Arrête proprement le thread télémétrie pour la clé donnée."""
    ev = _STOPS.get(key)
    if ev:
        ev.set()
    thr = _THREADS.get(key)
    if thr and thr.is_alive():
        try:
            thr.join(timeout=2.0)
        except Exception:
            pass
    _CACHES.pop(key, None)
    _STOPS.pop(key, None)
    _THREADS.pop(key, None)

def get_cache(key: Hashable) -> Optional[TelemetryCache]:
    """Récupère le cache de télémétrie associé à 'key' (ou None s'il n'existe pas)."""
    return _CACHES.get(key)
