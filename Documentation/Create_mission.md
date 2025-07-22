# Documentation – `create_mission` dans `mission_tool.py`

## Objectif

La fonction `create_mission` permet de générer un fichier de mission `.waypoints` compatible avec **QGroundControl (QGC)**.
Ce fichier contient la séquence de points GPS à suivre par un drone via MAVLink.

---

## Format de fichier généré

Chaque fichier `.waypoints` commence par l’en-tête :

```txt
QGC WPL 110
```

Puis chaque ligne décrit un waypoint :

```txt
seq    current    frame    command    param1    param2    param3    param4    lat    lon    alt    autoContinue
```

**Champs principaux :**

| Champ       | Description |
|-------------|-------------|
| `seq`       | Numéro de séquence du waypoint |
| `current`   | 1 si actif au démarrage (généralement 1 pour seq=0, sinon 0) |
| `frame`     | 0 = global absolu, 3 = global relative altitude |
| `command`   | 16 = WAYPOINT, 22 = TAKEOFF, 21 = LAND, etc. |
| `param1-4`  | Paramètres MAVLink (dépendent du `command`) |
| `lat/lon/alt` | Coordonnées GPS et altitude |
| `autoContinue` | 1 = passer automatiquement au suivant |

---

## Modes d’utilisation

### 🔹 Mode `auto` (par défaut)

- Utilise automatiquement la position actuelle du drone (via `get_flight_info(drone_id)`).
- Crée automatiquement :
  1. Point **Home** (position actuelle, `command=16`)
  2. Point **Takeoff** (`command=22`, avec `altitude_takeoff`)
  3. Waypoints utilisateur (si fournis)
  4. Point **Land** (`command=21`, position du dernier WP, altitude=0)

🔸 Remarque : le dernier point est **toujours forcé à LAND** en mode auto.

### 🔹 Mode `man`

- Tous les points sont fournis manuellement via `waypoints`.
- Aucun ajout automatique (ni Home, ni Takeoff, ni Land).
- Vous devez inclure toutes les séquences et paramètres vous-même.

---

## Exemples de JSON utilisés avec l’API ou en ligne de commande

### Mode `auto` avec 1 waypoint cible

```json
{
  "filename": "missions/mission_auto.waypoints",
  "altitude_takeoff": 30,
  "mode": "auto",
  "waypoints": [
    {
      "lat": 48.8585,
      "lon": 2.2950,
      "alt": 30
    }
  ]
}
```

### Mode `man` avec 4 points définis

```json
{
  "filename": "missions/mission_man.waypoints",
  "altitude_takeoff": 30,
  "mode": "man",
  "waypoints": [
    {
      "seq": 0,
      "current": 1,
      "frame": 0,
      "command": 16,
      "param1": 0,
      "param2": 0,
      "param3": 0,
      "param4": 0,
      "lat": 48.8566,
      "lon": 2.3522,
      "alt": 10,
      "autoContinue": 1
    },
    {
      "seq": 1,
      "current": 0,
      "frame": 0,
      "command": 22,
      "param1": 0,
      "param2": 0,
      "param3": 0,
      "param4": 0,
      "lat": 48.8566,
      "lon": 2.3522,
      "alt": 30,
      "autoContinue": 1
    },
    {
      "seq": 2,
      "current": 0,
      "frame": 3,
      "command": 16,
      "lat": 48.8570,
      "lon": 2.3530,
      "alt": 30,
      "param1": 0,
      "param2": 0,
      "param3": 0,
      "param4": 0,
      "autoContinue": 1
    },
    {
      "seq": 3,
      "current": 0,
      "frame": 3,
      "command": 21,
      "lat": 48.8570,
      "lon": 2.3530,
      "alt": 0,
      "param1": 0,
      "param2": 0,
      "param3": 0,
      "param4": 0,
      "autoContinue": 1
    }
  ]
}
```

---

## Ligne de commande (CLI)

```bash
python mission_tool.py create mission_auto.json
```

Ou :

```bash
python mission_tool.py send missions/mission_auto.waypoints
```

---

## Résumé des commandes MAVLink utilisées

| Commande | Description            |
|----------|------------------------|
| 16       | NAV_WAYPOINT           |
| 22       | NAV_TAKEOFF            |
| 21       | NAV_LAND               |

---

## Personnalisation avancée

Tu peux appeler la fonction directement depuis Python :

```python
from mission_tool import create_mission

create_mission("custom.waypoints", 30, custom_wp, mode="man")
```
