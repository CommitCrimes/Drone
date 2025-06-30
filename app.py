from flask import Flask, jsonify, request
import subprocess

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

if __name__ == '__main__':
    app.run(debug=True)
