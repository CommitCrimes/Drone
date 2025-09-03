# Documentation – `create_mission` dans `mission_tool.py`

## 🎯 Objectif
La fonction **`create_mission`** génère un fichier de mission `.waypoints` compatible avec **QGroundControl (QGC)**.  
Ce fichier contient la séquence de points GPS que le drone suivra via MAVLink.

---

## 📂 Signature

```python
def create_mission(
    master,
    filename,
    altitude_takeoff,
    waypoints=None,
    mode="auto",
    startlat=None,
    startlon=None,
    startalt=None,
    drone_id=None,
) -> str
```

### Paramètres
- `master` : lien MAVLink (`pymavlink`) utilisé pour récupérer la position si besoin.  
- `filename` : chemin du fichier `.waypoints` (sera écrit dans `./missions` si relatif).  
- `altitude_takeoff` : altitude cible du décollage (m).  
- `waypoints` : liste de waypoints utilisateur (facultatif).  
- `mode` : `"auto"` (ajoute automatiquement Home/Takeoff/Land) ou `"man"` (utilise les WPs fournis tels quels).  
- `startlat`, `startlon`, `startalt` : forcer la position de départ (sinon récupérée via `flight_info`).  
- `drone_id` : identifiant du drone à passer à `flight_info` (multi-drone).  

### Retour
- Chemin absolu du fichier `.waypoints` généré.

---

## 📑 Format de fichier généré

En-tête obligatoire :

```txt
QGC WPL 110
```

Chaque ligne suivante :  

```txt
seq    current    frame    command    param1    param2    param3    param4    lat    lon    alt    autoContinue
```

### Champs principaux

| Champ       | Description |
|-------------|-------------|
| `seq`       | Index du waypoint (0..N-1) |
| `current`   | 1 si actif au démarrage (souvent 1 pour seq=0) |
| `frame`     | 0 = global absolu (AMSL), 3 = global relative altitude (AGL) |
| `command`   | 16 = NAV_WAYPOINT, 22 = NAV_TAKEOFF, 21 = NAV_LAND |
| `param1..4` | Paramètres MAVLink dépendant de la commande |
| `lat/lon/alt` | Coordonnées GPS (WGS84) et altitude (m) |
| `autoContinue` | 1 = passer automatiquement au waypoint suivant |

---

## 🚀 Modes d’utilisation

### 🔹 Mode `auto` (par défaut)
1. Récupère la position de départ (`startlat/lon/alt` ou via `flight_info`).  
2. Ajoute automatiquement :
   - **WP 0** : point de départ (`command=16`)  
   - **WP 1** : décollage (`command=22`, `altitude_takeoff`)  
   - **WPs utilisateur** (seq ≥ 2)  
   - **Dernier WP** → forcé en **LAND** (`command=21`, alt=0)  

### 🔹 Mode `man`
- Aucun ajout automatique.  
- Tous les champs des WPs doivent être fournis (seq, frame, command, lat, lon, alt, …).  

---

## 📝 Exemples JSON

### Exemple simple en mode `auto`

```json
{
  "filename": "missions/mission_auto.waypoints",
  "altitude_takeoff": 30,
  "mode": "auto",
  "waypoints": [
    {"lat": 48.8585, "lon": 2.2950, "alt": 30}
  ]
}
```

### Exemple complet en mode `man`

```json
{
  "filename": "missions/mission_man.waypoints",
  "altitude_takeoff": 30,
  "mode": "man",
  "waypoints": [
    {"seq":0,"current":1,"frame":0,"command":16,"param1":0,"param2":0,"param3":0,"param4":0,"lat":48.8566,"lon":2.3522,"alt":10,"autoContinue":1},
    {"seq":1,"current":0,"frame":0,"command":22,"param1":0,"param2":0,"param3":0,"param4":0,"lat":48.8566,"lon":2.3522,"alt":30,"autoContinue":1},
    {"seq":2,"current":0,"frame":3,"command":16,"lat":48.8570,"lon":2.3530,"alt":30,"param1":0,"param2":0,"param3":0,"param4":0,"autoContinue":1},
    {"seq":3,"current":0,"frame":3,"command":21,"lat":48.8570,"lon":2.3530,"alt":0,"param1":0,"param2":0,"param3":0,"param4":0,"autoContinue":1}
  ]
}
```

---

## 💻 Utilisation en CLI

Créer une mission depuis un JSON :  
```bash
python mission_tool.py create mission_auto.json
```

Envoyer la mission au drone :  
```bash
python mission_tool.py send missions/mission_auto.waypoints
```

Modifier un waypoint existant :  
```bash
python mission_tool.py modify missions/mission_auto.waypoints 2 lat=48.86 lon=2.34 alt=50
```

Télécharger la mission depuis le drone :  
```bash
python mission_tool.py download missions/mission_from_drone.waypoints
```

---

## 📡 Rappels MAVLink

| Commande | Constante      | Description |
|----------|----------------|-------------|
| `16`     | NAV_WAYPOINT   | Aller à un point GPS |
| `22`     | NAV_TAKEOFF    | Décollage vertical |
| `21`     | NAV_LAND       | Atterrissage |

---

## 🔧 Notes
- En mode `auto`, le dernier waypoint est **converti en LAND** (alt=0).  
- Le répertoire `missions/` est créé automatiquement si nécessaire.  
