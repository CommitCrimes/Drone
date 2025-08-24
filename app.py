# app.py (version simplifiée/multi-drones, mêmes noms de fonctions)
import os, json, threading
from collections import OrderedDict
from typing import Dict, Tuple, Optional
from flask import Flask, jsonify, request, Response
from pymavlink import mavutil

from telemetry import telemetry_reader, TelemetryCache
from get_flight_info import build_flight_info
from init_log import logger
from mission_tool import create_mission, send_mission, modify_mission, download_mission
from start_mission import start

# ─────────────────────────────────────────────
# Config & registre
# ─────────────────────────────────────────────
with open("config.json", "r") as f:
    CONFIG = json.load(f)

DRONES: Dict[int, Dict[str, object]] = {}

app = Flask(__name__)

for d in CONFIG.get("drones", []):
    did = int(d["id"])
    url = str(d["conn"])
    baud = int(d.get("baud", 57600))

    master = mavutil.mavlink_connection(url, baud=baud)
    master.wait_heartbeat()
    logger.info(f"[drone {did}] Heartbeat via {url}")

    cache = TelemetryCache()
    stop_evt = threading.Event()
    t = threading.Thread(target=telemetry_reader, args=(master, cache, stop_evt), daemon=True)
    t.start()
    logger.info(f"[drone {did}] Thread télémétrie démarré")

    DRONES[did] = {"master": master, "cache": cache, "stop": stop_evt}

def _get_drone_or_404(drone_id: int) -> Tuple[Optional[Dict[str, object]], Optional[Tuple[Response, int]]]:
    entry = DRONES.get(drone_id)
    if not entry:
        return None, (jsonify(error=f"Drone {drone_id} introuvable"), 404)
    return entry, None

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────
@app.get("/")
def root():
    response = OrderedDict(
        status="ok",
        drones=[{"id": d["id"], "conn": d["conn"], "connected": (int(d["id"]) in DRONES)}
                for d in CONFIG.get("drones", [])]
    )
    logger.info("GET /")
    return Response(json.dumps(response), mimetype="application/json")

@app.get("/drones")
def list_drones():
    return jsonify([{"id": did, "connected": True} for did in sorted(DRONES.keys())])

@app.get("/drones/<int:drone_id>/flight_info")
def api_flight_info(drone_id: int):
    entry, err = _get_drone_or_404(drone_id)
    if err: return err
    strict = request.args.get('strict') in ('1', 'true', 'True')
    data = build_flight_info(drone_id, entry["cache"], allow_stale=not strict)  
    if data.get("stale"):
        logger.warning(f"[{drone_id}] Télémétrie stale: {data.get('age_sec')}")
    return jsonify(data), 200

@app.post("/drones/<int:drone_id>/command")
def send_command(drone_id: int):
    entry, err = _get_drone_or_404(drone_id)
    if err: return err
    master = entry["master"]
    data = request.get_json(force=True)
    mode = str(data.get("mode", "")).upper()
    if not mode:
        return jsonify(error="Champ 'mode' requis"), 400
    if mode not in master.mode_mapping():
        return jsonify(error=f"Mode '{mode}' non supporté"), 400
    master.set_mode(master.mode_mapping()[mode])
    logger.info(f"[{drone_id}] Mode -> {mode}")
    return jsonify(message=f"Mode changé vers {mode}"), 200

@app.post("/drones/<int:drone_id>/start")
def start_mission_route(drone_id: int):
    entry, err = _get_drone_or_404(drone_id)
    if err: return err
    start(entry["master"])
    logger.info(f"[{drone_id}] start_mission lancé")
    return jsonify(message=f"Mission démarrée (drone {drone_id})"), 200

@app.post("/drones/<int:drone_id>/mission/create")
def api_create_mission(drone_id: int):
    entry, err = _get_drone_or_404(drone_id)
    if err: return err
    data = request.get_json(force=True)
    filename = data.get("filename", "mission.waypoints")
    altitude_takeoff = data.get("altitude_takeoff", 30)
    waypoints = data.get("waypoints", [])
    mode = data.get("mode", "auto")
    startlat = data.get("startlat")
    startlon = data.get("startlon")
    startalt = data.get("startalt")

    create_mission(
        entry["master"], filename, altitude_takeoff, waypoints, mode,
        startlat=startlat, startlon=startlon, startalt=startalt,
        drone_id=drone_id
    )
    return jsonify(message=f"Mission créée dans {filename}", filename=filename), 201

@app.post("/drones/<int:drone_id>/mission/send")
def api_send_mission(drone_id: int):
    entry, err = _get_drone_or_404(drone_id)
    if err: return err
    master = entry["master"]

    if "file" in request.files:
        file = request.files["file"]
        if not file.filename.endswith(".waypoints"):
            return jsonify(error="Le fichier doit être .waypoints"), 400
        filepath = os.path.join("/tmp", file.filename)
        file.save(filepath)
        send_mission(filepath, master)
        logger.info(f"[{drone_id}] Mission envoyée depuis upload: {file.filename}")
        return jsonify(message=f"Mission envoyée depuis {file.filename}"), 200

    data = request.get_json(silent=True) or {}
    filename = data.get("filename")
    if not filename:
        return jsonify(error="Aucun fichier reçu et aucun 'filename' fourni"), 400
    if not filename.endswith(".waypoints"):
        return jsonify(error="Le fichier doit être .waypoints"), 400

    filepath = filename if os.path.isabs(filename) else os.path.join("missions", filename)
    if not os.path.exists(filepath):
        return jsonify(error=f"Fichier introuvable: {filepath}"), 404

    send_mission(filepath, master)
    logger.info(f"[{drone_id}] Mission envoyée: {filepath}")
    return jsonify(message=f"Mission envoyée depuis {filepath}"), 200

@app.post("/drones/<int:drone_id>/mission/modify")
def api_modify_mission(drone_id: int):
    data = request.get_json(force=True)
    filename = data["filename"]
    seq = int(data["seq"])
    updates = data["updates"]

    filepath = filename
    if not os.path.isabs(filepath):
        if not filepath.startswith("missions" + os.sep) and not filepath.startswith("missions/"):
            filepath = os.path.join("missions", filepath)
    if not os.path.exists(filepath):
        return jsonify(error=f"Fichier introuvable: {filepath}"), 404

    modify_mission(filepath, seq, updates)
    logger.info(f"[{drone_id}] Mission modifiée: {filepath} seq={seq}")
    return jsonify(message="Mission modifiée"), 200

@app.get("/drones/<int:drone_id>/mission/current")
def api_mission_current(drone_id: int):
    entry, err = _get_drone_or_404(drone_id)
    if err: return err
    items = download_mission(entry["master"])
    return jsonify({"count": len(items), "items": items}), 200

if __name__ == "__main__":
    logger.info("Démarrage API Flask multi-drones (debug)")
    app.run(debug=False, host="0.0.0.0", port=5000)
