import time, threading
from typing import Dict, Any, Optional, Hashable
from pymavlink import mavutil

# Verrou I/O MAVLink partagé (évite les collisions avec d'autres threads, ex: missions)
MAVLINK_IO_LOCK = threading.RLock()

# ─────────────────────────────────────────────
# Classe : TelemetryCache
# But : Stocker les derniers messages de télémétrie reçus
# Champs gérés :
#   - HEARTBEAT
#   - GLOBAL_POSITION_INT
#   - BATTERY_STATUS
# Étapes :
#   - update_from_msg() : met à jour les derniers messages
#   - snapshot() : retourne une copie des données courantes + timestamps
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
# Fonction : telemetry_reader
# But : Boucle de lecture MAVLink → met à jour le TelemetryCache
# Étapes :
#   - Demande un flux de télémétrie (DATA_STREAM_ALL)
#   - Ignore les messages liés aux missions
#   - Met à jour le cache avec les messages valides (heartbeat, position, batterie…)
#   - Boucle tant que stop_event n’est pas déclenché
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
# Multi-drones : registre
# But : gérer plusieurs threads/caches télémétrie en parallèle (1 par drone)
# Structures globales :
#   - _CACHES  : key → TelemetryCache
#   - _STOPS   : key → threading.Event (arrêt)
#   - _THREADS : key → Thread lecteur
#   - GLOBAL_CACHE : cache legacy par défaut
# ─────────────────────────────────────────────
_CACHES: Dict[Hashable, TelemetryCache] = {}
_STOPS: Dict[Hashable, threading.Event] = {}
_THREADS: Dict[Hashable, threading.Thread] = {}

# Rétro-compat (si on appelle sans key/cache)
GLOBAL_CACHE = TelemetryCache()
_LEGACY_KEY: Hashable = "__legacy__"

# ─────────────────────────────────────────────
# Fonction : start_telemetry_reader
# But : Lancer un thread de lecture télémétrie pour un drone donné
# Étapes :
#   - Détermine la clé (key) : drone_id, id(master) ou mode legacy
#   - Crée un TelemetryCache si nécessaire
#   - Lance le thread telemetry_reader si pas déjà actif
#   - Retourne le cache associé
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# Fonction : stop_telemetry_reader
# But : Arrêter un thread de lecture télémétrie actif
# Étapes :
#   - Déclenche l’event d’arrêt
#   - Join() le thread avec timeout
#   - Nettoie les dictionnaires globaux (_CACHES, _STOPS, _THREADS)
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# Fonction : get_cache
# But : Récupérer le TelemetryCache associé à une clé
# Étapes :
#   - Vérifie si la clé existe dans _CACHES
#   - Retourne l’objet TelemetryCache ou None
# ─────────────────────────────────────────────
def get_cache(key: Hashable) -> Optional[TelemetryCache]:
    """Récupère le cache de télémétrie associé à 'key' (ou None s'il n'existe pas)."""
    return _CACHES.get(key)
