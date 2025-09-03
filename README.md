# Drone API

Ce projet permet de contrôler des drones (réels ou en simulation) via une **API web Flask**.  
Il s’appuie sur **pymavlink** pour communiquer avec les drones et propose des endpoints HTTP pour gérer les missions au format `.waypoints`.

---

## 📂 Structure du projet

```txt
├── app.py                 # API Flask multi-drones
├── config.json            # Configuration des drones (connexions MAVLink)
├── get_flight_info.py     # Lecture des infos de vol (position, vitesse…)
├── init_log.py            # Configuration du logger
├── mission_tool.py        # Gestion des missions (create, send, modify, download, list)
├── return_to_home.py      # Commande RTL (Return to Launch)
├── start_mission.py       # Démarrage d’une mission
├── telemetry.py           # Thread + cache pour la télémétrie
├── missions/              # Répertoire des fichiers .waypoints
├── logs/                  # Logs générés
├── Documentation/         # Guides Markdown (ex: Create_mission.md)
├── test/                  # Scripts de test (WebSocket, communications…)
├── requirements.txt       # Dépendances Python
└── README.md              # Ce fichier
```

---

## 🚀 Installation & lancement

### 1. Installer les dépendances

Assure-toi d’avoir Python ≥ 3.8 puis :

```bash
pip install -r requirements.txt
```

### 2. Lancer l’API

```bash
python app.py
```

Par défaut, l’API écoute sur **http://0.0.0.0:5000**

---

## 🛰️ Simulation SITL (ArduPilot)

Pour tester sans drone physique, lance un simulateur ArduCopter :

```bash
cd ~/Projects/drone-sitl/ardupilot/Tools/autotest
./sim_vehicle.py -v ArduCopter -f quad --console --map --out=udp:127.0.0.1:14550
```

---

## 📡 Endpoints disponibles

### Informations générales
- **GET /** → Statut de l’API + liste des drones configurés  
- **GET /drones** → Liste des drones connectés  
- **GET /missions** → Liste les fichiers de mission (.waypoints)

### Télémétrie
- **GET /drones/<id>/flight_info** → Infos de vol (position, vitesse, batterie…)

### Missions
- **POST /drones/<id>/mission/create** → Créer une mission `.waypoints`
- **POST /drones/<id>/mission/send** → Envoyer une mission au drone
- **POST /drones/<id>/mission/modify** → Modifier un waypoint dans une mission
- **GET /drones/<id>/mission/current** → Télécharger la mission active

### Commandes
- **POST /drones/<id>/command** → Changer le mode de vol (`GUIDED`, `AUTO`, `RTL`…)
- **POST /drones/<id>/start** → Démarrer la mission en cours

---

## ⚙️ Comment ça marche

- `mission_tool.py` contient les fonctions principales :  
  `create_mission()`, `send_mission()`, `modify_mission()`, `download_mission()`, `list_missions()`  
- `start_mission.py` démarre la mission en utilisant le fichier `.waypoints`  
- `return_to_home.py` envoie une commande RTL (Return To Launch)  
- `telemetry.py` gère la réception et le cache des messages MAVLink  
- `get_flight_info.py` fournit la position, vitesse et état du drone

---

## 📖 Documentation complémentaire

Voir le dossier `Documentation/` :  
- `Create_mission.md` → détails sur la génération de missions  
- `guide_waypoints.md` → guide sur le format `.waypoints`
