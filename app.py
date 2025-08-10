import os
import json
import subprocess
from collections import OrderedDict
from flask import Flask, jsonify, request, Response

from get_flight_info import flight_info
from start_mission import start
from mission_tool import create_mission, send_mission, modify_mission
from pymavlink import mavutil

from init_log import logger  # Ajout du logger

# ─────────────────────────────────────────────
# Charger la configuration du drone
# ─────────────────────────────────────────────
with open("config.json", "r") as f:
    config = json.load(f)
drone_id = config.get("drone_id", "undefined")

# ─────────────────────────────────────────────
# Initialisation de Flask et de MAVLink
# ─────────────────────────────────────────────
app = Flask(__name__)
logger.info("Connexion MAVLink en cours...")
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()
logger.info("Heartbeat MAVLink reçu")

# ─────────────────────────────────────────────
# GET /
@app.route('/')
def hello_world():
    response = OrderedDict()
    response["status"] = "ok"
    response["message"] = f"API du drone: {drone_id}"
    logger.info("Requête GET /")
    return Response(json.dumps(response), mimetype='application/json')

# ─────────────────────────────────────────────
# POST /start
@app.route('/start', methods=['POST'])
def start_mission():
    try:
        start(master)
        logger.info("Script start_mission.py lancé")
        return jsonify(message="Script start_mission.py lancé"), 200
    except Exception as e:
        logger.error(f"Erreur start_mission: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /mission/create
@app.route('/mission/create', methods=['POST'])
def api_create_mission():
    try:
        data = request.get_json()
        filename = data.get("filename", "mission.waypoints")
        altitude_takeoff = data.get("altitude_takeoff", 30)
        waypoints = data.get("waypoints", [])
        mode = data.get("mode", "auto")

        create_mission(master, filename, altitude_takeoff, waypoints, mode)
        logger.info(f"Mission créée : {filename}, altitude={altitude_takeoff}, mode={mode}")
        return jsonify(message=f"Mission créée dans {filename}"), 200

    except Exception as e:
        logger.error(f"Erreur création mission: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /mission/send
@app.route('/mission/send', methods=['POST'])
def api_send_mission():
    try:
        if 'file' in request.files:
            file = request.files['file']
            if not file.filename.endswith('.waypoints'):
                logger.warning("Fichier non .waypoints rejeté")
                return jsonify(error="Le fichier doit avoir l'extension .waypoints"), 400

            filepath = os.path.join('/tmp', file.filename)
            file.save(filepath)

            send_mission(filepath, master)
            logger.info(f"Mission envoyée depuis fichier uploadé : {file.filename}")
            return jsonify(message=f"Mission envoyée depuis {file.filename}"), 200

        data = request.get_json(silent=True) or {}
        filename = data.get('filename')
        if not filename:
            logger.warning("Ni fichier uploadé ni 'filename' fourni")
            return jsonify(error="Aucun fichier reçu et aucun 'filename' fourni"), 400

        if not filename.endswith('.waypoints'):
            return jsonify(error="Le fichier doit avoir l'extension .waypoints"), 400

        filepath = filename
        if not os.path.isabs(filepath):
            if not filepath.startswith('missions' + os.sep) and not filepath.startswith('missions/'):
                filepath = os.path.join('missions', filepath)

        if not os.path.exists(filepath):
            logger.warning(f"Fichier introuvable: {filepath}")
            return jsonify(error=f"Fichier introuvable: {filepath}"), 404

        send_mission(filepath, master)
        logger.info(f"Mission envoyée depuis fichier existant : {filepath}")
        return jsonify(message=f"Mission envoyée depuis {filepath}"), 200

    except Exception as e:
        logger.error(f"Erreur envoi mission: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# GET /flight_info
@app.route('/flight_info', methods=['GET'])
def api_flight_info():
    try:
        data = flight_info(drone_id, master)
        logger.info("Données de vol récupérées")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Erreur récupération infos vol: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /command
@app.route('/command', methods=['POST'])
def send_command():
    try:
        data = request.get_json()
        mode = data.get("mode", "").upper()

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
        logger.error(f"Erreur changement de mode: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# Lancement de l'application
# ─────────────────────────────────────────────
if __name__ == '__main__':
    logger.info("Démarrage de l'API Flask du drone (mode debug)")
    app.run(debug=True)
