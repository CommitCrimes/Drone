# Drone

Ce projet permet de contrôler des missions drones via une API web en Flask. Il s'appuie sur **pymavlink** et permet de créer, lancer et rappeler des missions via des endpoints HTTP.

## Structure du projet

├── app.py # API Flask principale
├── create.py # Génère un fichier mission JSON
├── start_mission.py # Charge et envoie une mission au drone
├── return_to_home.py # Envoie une commande RTL (return to launch)
├── get_flight_info.py # Récupère la position et vitesse actuelle
├── mission.json # Fichier JSON contenant la mission
├── mission.py # Code principal pour gérer l'envoi de mission
└── README.md # Ce fichier

---

## Lancement de l'API

### 1. Installer les dépendances

Assure-toi d'avoir Python 3 installé, puis :

```bash
pip install flask pymavlink

python app.py
```
## lancer la simulation
cd Projects/drone-sitl/ardupilot/Tools/autotest
./sim_vehicle.py  -v ArduCopter -f quad --console --map --out=udp:127.0.0.1:14550

## Endpoints disponibles
🔸 GET /
Renvoie un message de test :

🔹 GET /flight_info
Renvoie la position et vitesse actuelle du drone :


🔸 POST /create
Crée une mission (fichier mission.json) via create.py.

curl -X POST http://localhost:5000/create
🔸 POST /start

Envoie la mission au drone via start_mission.py.
curl -X POST http://localhost:5000/start
🔸 POST /rth

Demande le retour au point de lancement (Return to Launch).
curl -X POST http://localhost:5000/rth

## Comment ça marche
mission.py contient les fonctions create_mission() et send_mission() utilisées par les scripts.
start_mission.py lit le fichier mission.json et envoie la mission au drone.
create.py génère un fichier mission.json contenant des waypoints.
return_to_home.py envoie une commande RTL au drone (via MAVLink).
get_flight_info.py écoute les messages MAVLink pour retourner la position et la vitesse sol

