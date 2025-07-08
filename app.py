from flask import Flask, jsonify, request
from flask import Flask, jsonify, Response

import subprocess
import json

from get_flight_info import get_flight_info
from mission_tool import create_mission, send_mission

app = Flask(__name__)

@app.route('/')
def hello_world():
    return jsonify(message="T'es mauvais jack")

@app.route('/start', methods=['POST'])
def start_mission():
    try:
        # Lancer le script Python en tâche de fond
        subprocess.Popen(['python3', 'start_mission.py'])
        return jsonify(message="Script start_mission.py lancé"), 200
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/rth', methods=['POST'])
def return_to_home():
    try:
        subprocess.Popen(['python3', 'return_to_home.py'])
        return jsonify(message="Script return_to_home lancé"), 200
    except Exception as e:
        return jsonify(error=str(e)), 500   
        
@app.route('/mission/create', methods=['POST'])
def api_create_mission():
    try:
        data = request.get_json()
        filename = data.get('filename', 'mission.json')
        waypoints = data.get('waypoints')
        create_mission(filename, waypoints)  # <-- ici
        return jsonify(message=f"Mission créée dans {filename}"), 200
    except Exception as e:
        return jsonify(error=str(e)), 500




@app.route('/mission/send', methods=['POST'])
def api_send_mission():
    try:
        filename = request.json.get('filename', 'mission.json')
        send_mission(filename)
        return jsonify(message=f"Mission envoyée depuis {filename}"), 200
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/flight_info', methods=['GET'])
def flight_info():
    try:
        data = get_flight_info()
        return jsonify(data), 200
    except Exception as e:
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/')
def hello_world():
    response = OrderedDict()
    response["status"] = "ok"
    response["message"] = "API du drone"

    return Response(json.dumps(response), mimetype='application/json')
