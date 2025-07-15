import os
from typing import OrderedDict
from flask import Flask, jsonify, request
from flask import Flask, jsonify, Response

import subprocess
import json

from get_flight_info import get_flight_info
from mission_tool import create_mission, send_mission, modify_mission
from init_log import logger

# ─────────────────────────────────────────────
# Charger la configuration du drone
# ─────────────────────────────────────────────

with open("config.json", "r") as f:
    config = json.load(f)

# Accéder aux valeurs
drone_id = config["drone_id"]

# ─────────────────────────────────────────────
# Initialisation de l'application Flask
# ─────────────────────────────────────────────
app = Flask(__name__)


# ─────────────────────────────────────────────
# Route GET / — Route test
# ─────────────────────────────────────────────
@app.route('/')
def hello_world():
    return jsonify(message="API du drone: " + str(drone_id))

# ─────────────────────────────────────────────
# Route POST /start — Lancer une mission
# Lance le script `start_mission.py` en tâche de fond
# ─────────────────────────────────────────────
@app.route('/start', methods=['POST'])
def start_mission():
    try:
        # Lancer le script Python en tâche de fond
        subprocess.Popen(['python3', 'start_mission.py'])
        logger.info("Script start_mission.py lancé")
        return jsonify(message="Script start_mission.py lancé"), 200
    except Exception as e:
        logger.error(f"Erreur start_mission: {str(e)}")
        return jsonify(error=str(e)), 500
    
# ─────────────────────────────────────────────
# Route POST /land — Fait atterir le Drone
# Lance le script `land.py` en tâche de fond
# ─────────────────────────────────────────────
@app.route('/land', methods=['POST'])
def land():
    try:
        # Lancer le script Python en tâche de fond
        subprocess.Popen(['python3', 'land.py'])
        logger.info("Script land.py lancé")
        return jsonify(message="Script land.py lancé"), 200
    except Exception as e:
        logger.error(f"Erreur land: {str(e)}")
        return jsonify(error=str(e)), 500

# ─────────────────────────────────────────────
# Route POST /rth — Return To Home
# Lance le script `return_to_home.py` en tâche de fond
# ─────────────────────────────────────────────
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
# Route POST /mission/create
# Crée une mission .waypoints (mode auto ou man)
# Requiert un body JSON contenant :
# {
#   "filename": "missions/xxx.waypoints",
#   "altitude_takeoff": 30,
#   "waypoints": [voir dans la docu],
#   "mode": "auto" | "man"
# }
# ─────────────────────────────────────────────
@app.route('/mission/create', methods=['POST'])
def api_create_mission():
    try:
        data = request.get_json()

        filename = data.get("filename", "mission.waypoints")
        altitude_takeoff = data.get("altitude_takeoff", 30)
        waypoints = data.get("waypoints", [])
        mode = data.get("mode", "auto")

        # Appel correct avec 4 arguments
        create_mission(filename, altitude_takeoff, waypoints, mode)
        logger.info(f"Mission créée : {filename}, mode={mode}, altitude={altitude_takeoff}")
        return jsonify(message=f"Mission créée dans {filename}"), 200

    except Exception as e:
        logger.error(f"Erreur création mission: {str(e)}")
        return jsonify(error=str(e)), 500



# ─────────────────────────────────────────────
# Route POST /mission/send
# Envoie un fichier .waypoints au drone
# Body attendu : un fichier (missions/fichier.waypoints)
# ─────────────────────────────────────────────
@app.route('/mission/send', methods=['POST'])
def api_send_mission():
    try:
        if 'file' not in request.files:
            logger.warning("Aucun fichier reçu pour /mission/send")
            return jsonify(error="Aucun fichier reçu"), 400

        file = request.files['file']
        if not file.filename.endswith('.waypoints'):
            logger.warning("Fichier invalide reçu (pas .waypoints)")
            return jsonify(error="Le fichier doit avoir l'extension .waypoints"), 400

        # Sauvegarder le fichier temporairement
        filepath = os.path.join('/tmp', file.filename)
        file.save(filepath)

        # Appeler la fonction de mission
        send_mission(filepath)
        logger.info(f"Mission envoyée depuis fichier : {file.filename}")
        return jsonify(message=f"Mission envoyée depuis {file.filename}"), 200

    except Exception as e:
        logger.error(f"Erreur envoi mission: {str(e)}")
        return jsonify(error=str(e)), 500

@app.route('/mission/modify', methods=['POST'])

# ─────────────────────────────────────────────
# Route POST /mission/modify
# Modifie un waypoint existant dans un fichier .waypoints
# Requiert un body JSON contenant :
# {
#   "filename": "missions/xxx.waypoints",  ← chemin du fichier
#   "seq": 3,                              ← numéro du waypoint à modifier
#   "updates": {                           ← dictionnaire des champs à modifier
#     "lat": 48.8599,
#     "lon": 2.2959,
#     "alt": 140,
#     "command": 16,
#     ...
#   }
# }
# Renvoie :
#   - 200 OK si modification réussie
#   - 400 si données invalides
#   - 500 si une erreur interne survient
# ─────────────────────────────────────────────
def api_modify_mission():
    try:
        data = request.get_json()   

        filename = data.get("filename")
        seq = data.get("seq")
        updates = data.get("updates", {})

        if not filename or seq is None or not isinstance(updates, dict):
            logger.warning("Données invalides pour /mission/modify")
            return jsonify(error="Champs 'filename', 'seq' et 'updates' requis"), 400

        modify_mission(filename, int(seq), updates)
        logger.info(f"Waypoint {seq} modifié dans {filename} avec {updates}")
        return jsonify(message=f"Waypoint {seq} modifié dans {filename}"), 200

    except Exception as e:
        return jsonify(error=str(e)), 500


# ─────────────────────────────────────────────
# Route GET /flight_info
# Retourne les infos de vol actuelles du drone
# ─────────────────────────────────────────────
@app.route('/flight_info', methods=['GET'])
def flight_info():
    try:
        data = get_flight_info(drone_id)
        logger.info("Données de vol récupérées avec succès")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Erreur récupération données vol: {str(e)}")
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    logger.info("Démarrage de l'API Flask du drone")
    app.run(debug=True)

@app.route('/')
def hello_world():
    response = OrderedDict()
    response["status"] = "ok"
    response["message"] = "API du drone"

    return Response(json.dumps(response), mimetype='application/json')

