import os
import json
from collections import OrderedDict
from flask import Flask, jsonify, request, Response
from pymavlink import mavutil
from telemetry import start_telemetry_reader, GLOBAL_CACHE
from get_flight_info import build_flight_info, flight_info as flight_info_direct

from init_log import logger
from mission_tool import create_mission, send_mission, modify_mission
from start_mission import start

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
with open("config.json", "r") as f:
    config = json.load(f)
drone_id = config.get("drone_id", "undefined")

# ─────────────────────────────────────────────
# Flask & MAVLink
# ─────────────────────────────────────────────
app = Flask(__name__)

logger.info("Connexion MAVLink…")
master = mavutil.mavlink_connection("udp:127.0.0.1:14550")
master.wait_heartbeat()
logger.info("Heartbeat MAVLink reçu")

# Thread télémétrie
start_telemetry_reader(master)
logger.info("Thread télémétrie démarré")

# ─────────────────────────────────────────────
@app.route("/")
def hello_world():
    response = OrderedDict(status="ok", message=f"API du drone: {drone_id}")
    logger.info("GET /")
    return Response(json.dumps(response), mimetype="application/json")


# ─────────────────────────────────────────────
# POST /start
@app.route("/start", methods=["POST"])
def start_mission_route():
    try:
        start(master)
        logger.info("Script start_mission.py lancé")
        return jsonify(message="Script start_mission.py lancé"), 200
    except Exception as e:
        logger.exception("Erreur start_mission")
        return jsonify(error=str(e)), 500


# ─────────────────────────────────────────────
# POST /mission/create
@app.route("/mission/create", methods=["POST"])
def api_create_mission():
    try:
        data = request.get_json(force=True)
        filename = data.get("filename", "mission.waypoints")
        altitude_takeoff = data.get("altitude_takeoff", 30)
        waypoints = data.get("waypoints", [])
        mode = data.get("mode", "auto")

        create_mission(master, filename, altitude_takeoff, waypoints, mode)
        logger.info(f"Mission créée : {filename}, altitude={altitude_takeoff}, mode={mode}")
        return jsonify(message=f"Mission créée dans {filename}"), 200
    except Exception as e:
        logger.exception("Erreur création mission")
        return jsonify(error=str(e)), 500


# ─────────────────────────────────────────────
# POST /mission/send
@app.route("/mission/send", methods=["POST"])
def api_send_mission():
    try:
        # Upload direct
        if "file" in request.files:
            file = request.files["file"]
            if not file.filename.endswith(".waypoints"):
                logger.warning("Fichier non .waypoints rejeté")
                return jsonify(error="Le fichier doit avoir l'extension .waypoints"), 400

            filepath = os.path.join("/tmp", file.filename)
            file.save(filepath)
            send_mission(filepath, master)
            logger.info(f"Mission envoyée depuis fichier uploadé : {file.filename}")
            return jsonify(message=f"Mission envoyée depuis {file.filename}"), 200

        # Ou référence à un fichier existant
        data = request.get_json(silent=True) or {}
        filename = data.get("filename")
        if not filename:
            logger.warning("Ni fichier uploadé ni 'filename' fourni")
            return jsonify(error="Aucun fichier reçu et aucun 'filename' fourni"), 400

        if not filename.endswith(".waypoints"):
            return jsonify(error="Le fichier doit avoir l'extension .waypoints"), 400

        filepath = filename
        if not os.path.isabs(filepath):
            if not filepath.startswith("missions" + os.sep) and not filepath.startswith("missions/"):
                filepath = os.path.join("missions", filepath)

        if not os.path.exists(filepath):
            logger.warning(f"Fichier introuvable: {filepath}")
            return jsonify(error=f"Fichier introuvable: {filepath}"), 404

        send_mission(filepath, master)
        logger.info(f"Mission envoyée depuis fichier existant : {filepath}")
        return jsonify(message=f"Mission envoyée depuis {filepath}"), 200

    except Exception as e:
        logger.exception("Erreur envoi mission")
        return jsonify(error=str(e)), 500


# ─────────────────────────────────────────────
# POST /mission/modify
@app.route("/mission/modify", methods=["POST"])
def api_modify_mission():
    try:
        data = request.get_json(force=True)
        filename = data["filename"]
        seq = int(data["seq"])
        updates = data["updates"]
        modify_mission(master, filename, seq, updates)
        logger.info(f"Mission modifiée : {filename} seq={seq}")
        return jsonify(message="Mission modifiée"), 200
    except Exception as e:
        logger.exception("Erreur modification mission")
        return jsonify(error=str(e)), 500


# ─────────────────────────────────────────────
# GET /flight_info
@app.route("/flight_info", methods=["GET"])
def api_flight_info():
    try:
        # on peut garder un query param si tu veux forcer strict:
        # ?strict=1 retournera 503 si stale
        strict = request.args.get('strict') in ('1', 'true', 'True')
        data = build_flight_info(drone_id, GLOBAL_CACHE, allow_stale=not strict)
        if data.get("stale"):
            logger.warning("Télémétrie stale: ages=%s", data.get("age_sec"))
        else:
            logger.info("Données de vol récupérées (cache)")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Erreur récupération infos vol: {str(e)}")
        return jsonify(error=str(e)), 503

    

# ─────────────────────────────────────────────
# POST /command
@app.route("/command", methods=["POST"])
def send_command():
    try:
        data = request.get_json(force=True)
        mode = str(data.get("mode", "")).upper()

        if not mode:
            logger.warning("Champ 'mode' manquant dans /command")
            return jsonify(error="Champ 'mode' requis"), 400

        if mode not in master.mode_mapping():
            logger.warning(f"Mode '{mode}' non supporté")
            return jsonify(error=f"Mode '{mode}' non supporté"), 400

        mode_id = master.mode_mapping()[mode]
        master.set_mode(mode_id)
        logger.info(f"Mode changé vers {mode}")
        return jsonify(message=f"Mode changé vers {mode}"), 200

    except Exception as e:
        logger.exception("Erreur changement de mode")
        return jsonify(error=str(e)), 500


# ─────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Démarrage de l'API Flask du drone (debug)")
    app.run(debug=True, host="0.0.0.0", port=5000)
