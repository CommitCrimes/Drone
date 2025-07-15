import os
import json
import subprocess
from collections import OrderedDict
from flask import Flask, jsonify, request, Response

from get_flight_info import get_flight_info
from mission_tool import create_mission, send_mission, modify_mission
from pymavlink import mavutil

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
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()

# ─────────────────────────────────────────────
# GET /
# Test de l’API
# ─────────────────────────────────────────────
@app.route('/')
def hello_world():
    response = OrderedDict()
    response["status"] = "ok"
    response["message"] = f"API du drone: {drone_id}"
    return Response(json.dumps(response), mimetype='application/json')

# ─────────────────────────────────────────────
# POST /start
# Lance le script de mission
# ─────────────────────────────────────────────
@app.route('/start', methods=['POST'])
def start_mission():
    try:
        subprocess.Popen(['python3', 'start_mission.py'])
        return jsonify(message="Script start_mission.py lancé"), 200
    except Exception as e:
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /rth
# Retour au point de départ
# ─────────────────────────────────────────────
@app.route('/rth', methods=['POST'])
def return_to_home():
    try:
        subprocess.Popen(['python3', 'return_to_home.py'])
        return jsonify(message="Script return_to_home lancé"), 200
    except Exception as e:
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /mission/create
# Crée une mission personnalisée
# ─────────────────────────────────────────────
@app.route('/mission/create', methods=['POST'])
def api_create_mission():
    try:
        data = request.get_json()
        filename = data.get("filename", "mission.waypoints")
        altitude_takeoff = data.get("altitude_takeoff", 30)
        waypoints = data.get("waypoints", [])
        mode = data.get("mode", "auto")

        create_mission(filename, altitude_takeoff, waypoints, mode)
        return jsonify(message=f"Mission créée dans {filename}"), 200

    except Exception as e:
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /mission/send
# Envoie un fichier .waypoints
# ─────────────────────────────────────────────
@app.route('/mission/send', methods=['POST'])
def api_send_mission():
    try:
        if 'file' not in request.files:
            return jsonify(error="Aucun fichier reçu"), 400

        file = request.files['file']
        if not file.filename.endswith('.waypoints'):
            return jsonify(error="Le fichier doit avoir l'extension .waypoints"), 400

        filepath = os.path.join('/tmp', file.filename)
        file.save(filepath)

        send_mission(filepath)
        return jsonify(message=f"Mission envoyée depuis {file.filename}"), 200

    except Exception as e:
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /mission/modify
# Modifie un waypoint
# ─────────────────────────────────────────────
@app.route('/mission/modify', methods=['POST'])
def api_modify_mission():
    try:
        data = request.get_json()
        filename = data.get("filename")
        seq = data.get("seq")
        updates = data.get("updates", {})

        if not filename or seq is None or not isinstance(updates, dict):
            return jsonify(error="Champs 'filename', 'seq' et 'updates' requis"), 400

        modify_mission(filename, int(seq), updates)
        return jsonify(message=f"Waypoint {seq} modifié dans {filename}"), 200

    except Exception as e:
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# GET /flight_info
# Donne les infos de vol en temps réel
# ─────────────────────────────────────────────
@app.route('/flight_info', methods=['GET'])
def flight_info():
    try:
        data = get_flight_info(drone_id)
        return jsonify(data), 200
    except Exception as e:
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# POST /command
# Changer le mode de vol (GUIDED, LOITER, etc.)
# ─────────────────────────────────────────────
@app.route('/command', methods=['POST'])
def send_command():
    try:
        data = request.get_json()
        mode = data.get("mode", "").upper()

        if not mode:
            return jsonify(error="Champ 'mode' requis"), 400

        if mode not in master.mode_mapping():
            return jsonify(error=f"Mode '{mode}' non supporté"), 400

        mode_id = master.mode_mapping()[mode]
        master.set_mode(mode_id)
        return jsonify(message=f"Mode changé vers {mode}"), 200

    except Exception as e:
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# Lancement de l'application
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
