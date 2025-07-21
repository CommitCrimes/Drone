import os
import json
import subprocess
from collections import OrderedDict
from flask import Flask, jsonify, request, Response
import queue
from init_log import logger

from get_flight_info import get_flight_info
from mission_tool import create_mission, send_mission, modify_mission
from mavlink_manager import command_queue, status_queue  # communication thread MAVLink

# ─────────────────────────────────────────────
# Charger la configuration du drone
# ─────────────────────────────────────────────
with open("config.json", "r") as f:
    config = json.load(f)
drone_id = config.get("drone_id", "undefined")
production = config.get("production", "undefined")
port = config.get("port", 5000)

# ─────────────────────────────────────────────
# Initialisation de Flask
# ─────────────────────────────────────────────
app = Flask(__name__)

# ─────────────────────────────────────────────
# GET /
@app.route('/')
def hello_world():
    response = OrderedDict()
    response["status"] = "ok"
    response["message"] = f"API du drone: {drone_id}"
    return Response(json.dumps(response), mimetype='application/json')

# ─────────────────────────────────────────────
# POST /start
@app.route('/start', methods=['POST'])
def start_mission():
    try:
        subprocess.Popen(['python3', 'start_mission.py'])
        logger.info("Script start_mission.py lancé")
        return jsonify(message="Script start_mission.py lancé"), 200
    except Exception as e:
        logger.error(f"Erreur start_mission: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /rth
@app.route('/rth', methods=['POST'])
def return_to_home():
    try:
        subprocess.Popen(['python3', 'return_to_home.py'])
        logger.info("Script return_to_home.py lancé")
        return jsonify(message="Script return_to_home lancé"), 200
    except Exception as e:
        logger.error(f"Erreur return_to_home: {str(e)}")
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

        create_mission(filename, altitude_takeoff, waypoints, mode)
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
        if 'file' not in request.files:
            logger.warning("Aucun fichier reçu pour /mission/send")
            return jsonify(error="Aucun fichier reçu"), 400

        file = request.files['file']
        if not file.filename.endswith('.waypoints'):
            logger.warning("Fichier non .waypoints rejeté")
            return jsonify(error="Le fichier doit avoir l'extension .waypoints"), 400

        filepath = os.path.join('/tmp', file.filename)
        file.save(filepath)

        send_mission(filepath)
        logger.info(f"Mission envoyée depuis fichier : {file.filename}")
        return jsonify(message=f"Mission envoyée depuis {file.filename}"), 200

    except Exception as e:
        logger.error(f"Erreur envoi mission: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /mission/modify
@app.route('/mission/modify', methods=['POST'])
def api_modify_mission():
    try:
        data = request.get_json()
        filename = data.get("filename")
        seq = data.get("seq")
        updates = data.get("updates", {})

        if not filename or seq is None or not isinstance(updates, dict):
            logger.warning("Requête invalide pour /mission/modify")
            return jsonify(error="Champs 'filename', 'seq' et 'updates' requis"), 400

        modify_mission(filename, int(seq), updates)
        logger.info(f"Waypoint {seq} modifié dans {filename} : {updates}")
        return jsonify(message=f"Waypoint {seq} modifié dans {filename}"), 200

    except Exception as e:
        logger.error(f"Erreur modification mission: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# GET /flight_info
@app.route('/flight_info', methods=['GET'])
def flight_info():
    try:
        data = get_flight_info(drone_id)
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

        command_queue.put({"type": "set_mode", "mode": mode})
        logger.info(f"Commande de changement de mode envoyée : {mode}")

        # On attend la réponse du thread MAVLink (timeout 3s)
        try:
            response = status_queue.get(timeout=3)
            if response.get("success"):
                return jsonify(message=response.get("message")), 200
            else:
                return jsonify(error=response.get("message")), 400
        except queue.Empty:
            logger.error("Timeout — aucune réponse du thread MAVLink")
            return jsonify(error="Pas de réponse du drone (timeout)"), 504

    except Exception as e:
        logger.error(f"Erreur changement de mode: {str(e)}")
        return jsonify(error=str(e)), 500



# ─────────────────────────────────────────────
# Lancement de l'application
# ─────────────────────────────────────────────
if __name__ == '__main__':
    logger.info("Démarrage de l'API Flask du drone")
    if production == "prod":
        logger.info(f"Mode : prod — port {port}")
        app.run(debug=False, host='0.0.0.0', port=port)
    elif production == "dev":
        logger.info(f"Mode : dev — port {port}")
        app.run(debug=True, port=port)
    else:
        logger.warning(f"Le mode config n’est ni dev ni prod : {production} — port {port}")
        app.run(debug=True, port=port)
