import json
import sys
from pymavlink import mavutil

import json
#Rajouter une premiere ligne pour le take off qui correspond a l'emplacement actuel du drone Faire une request Flight info pour récupérer la position
def create_mission(filename, altitude_takeoff, waypoints=None, mode="auto"):
    """
    Crée un fichier .waypoints compatible QGC

    Args:
        filename (str): nom du fichier à écrire
        altitude_takeoff (float): altitude du takeoff
        waypoints (list of dict): liste des waypoints (avec lat, lon, alt, etc)
        mode (str): "auto" ou "man"
    """

    mission_waypoints = []

    if mode == "man":
        # Mode manuel : waypoints complets attendus
        if not waypoints:
            raise ValueError("En mode 'man', il faut passer la liste complète de waypoints.")
        mission_waypoints = waypoints

    else:
        # Mode auto : on récupère la position actuelle du drone
        flight_info = get_flight_info()
        latitude = flight_info["latitude"]
        longitude = flight_info["longitude"]
        altitude = flight_info.get("altitude", altitude_takeoff)  # fallback si altitude non dispo

        # Home (seq=0)
        mission_waypoints.append({
            "seq": 0,
            "current": 1,
            "frame": 0,
            "command": 16,  # MAV_CMD_NAV_WAYPOINT
            "param1": 0,
            "param2": 0,
            "param3": 0,
            "param4": 0,
            "lat": latitude,
            "lon": longitude,
            "alt": altitude,
            "autoContinue": 1
        })

        # Takeoff (seq=1)
        mission_waypoints.append({
            "seq": 1,
            "current": 0,
            "frame": 0,
            "command": 22,  # MAV_CMD_NAV_TAKEOFF
            "param1": 0,
            "param2": 0,
            "param3": 0,
            "param4": 0,
            "lat": latitude,
            "lon": longitude,
            "alt": altitude_takeoff,
            "autoContinue": 1
        })

        # Ajout des autres waypoints à partir de seq=2
        if waypoints:
            for i, wp in enumerate(waypoints, start=2):
                mission_waypoints.append({
                    "seq": i,
                    "current": 0,
                    "frame": wp.get("frame", 3),
                    "command": wp.get("command", 16),
                    "param1": wp.get("param1", 0.0),
                    "param2": wp.get("param2", 0.0),
                    "param3": wp.get("param3", 0.0),
                    "param4": wp.get("param4", 0.0),
                    "lat": wp.get("lat", 0.0),
                    "lon": wp.get("lon", 0.0),
                    "alt": wp.get("alt", 100.0),
                    "autoContinue": wp.get("autoContinue", 1)
                })

        # Forcer le dernier point en LAND
        if mission_waypoints:
            mission_waypoints[-1]["command"] = 21  # MAV_CMD_NAV_LAND
            mission_waypoints[-1]["alt"] = 0

    # Écriture dans le fichier
    with open(filename, "w") as f:
        f.write("QGC WPL 110\n")
        for wp in mission_waypoints:
            line = (
                f"{wp['seq']}\t{wp['current']}\t{wp['frame']}\t{wp['command']}\t"
                f"{wp['param1']:.8f}\t{wp['param2']:.8f}\t{wp['param3']:.8f}\t{wp['param4']:.8f}\t"
                f"{wp['lat']:.8f}\t{wp['lon']:.8f}\t{wp['alt']:.6f}\t{wp['autoContinue']}\n"
            )
            f.write(line)

    print(f"Mission .waypoints créée : {filename}")

def send_mission(filename):
    from pymavlink import mavutil
    import time

    print(f"Chargement du fichier .waypoints : {filename}")

    # Lire et parser les waypoints depuis fichier texte
    with open(filename, 'r') as f:
        lines = f.readlines()

    if not lines[0].startswith("QGC WPL 110"):
        print("Format de fichier invalide. Attendu : 'QGC WPL 110'")
        return

    waypoints = []
    for line in lines[1:]:
        parts = line.strip().split('\t')
        if len(parts) != 12:
            continue
        wp = {
            "seq": int(parts[0]),
            "current": int(parts[1]),
            "frame": int(parts[2]),
            "command": int(parts[3]),
            "param1": float(parts[4]),
            "param2": float(parts[5]),
            "param3": float(parts[6]),
            "param4": float(parts[7]),
            "lat": float(parts[8]),
            "lon": float(parts[9]),
            "alt": float(parts[10]),
            "autoContinue": int(parts[11])
        }
        waypoints.append(wp)

    # Connexion MAVLink
    master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
    master.wait_heartbeat()
    print(f"Connecté à {master.target_system}/{master.target_component}")

    # Efface l'ancienne mission
    master.waypoint_clear_all_send()
    time.sleep(1)

    # Envoie le nombre de waypoints
    master.waypoint_count_send(len(waypoints))
    print(f"Envoi de {len(waypoints)} waypoints...")

    for wp in waypoints:
        msg = master.recv_match(type='MISSION_REQUEST', blocking=True, timeout=10)
        if msg and msg.seq == wp["seq"]:
            master.mav.mission_item_send(
                master.target_system,
                master.target_component,
                wp["seq"],
                wp["frame"],
                wp["command"],
                wp["current"],
                wp["autoContinue"],
                wp["param1"], wp["param2"], wp["param3"], wp["param4"],
                wp["lat"], wp["lon"], wp["alt"]
            )
            print(f"WP {wp['seq']} envoyé")
        else:
            print(f"Pas de demande pour WP {wp['seq']}")

    time.sleep(1)

    # Définit le waypoint courant à 0
    master.mav.mission_set_current_send(master.target_system, master.target_component, 0)
    print("Waypoint courant défini à 0")

    time.sleep(1)
    print("Mission envoyé")


# --- Point d'entrée ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Utilisation : python mission_tool.py [create|send] nom_fichier.json")
        sys.exit(1)

    action = sys.argv[1]
    fichier = sys.argv[2]

    if action == "create":
        create_mission(fichier)
    elif action == "send":
        send_mission(fichier)
    else:
        print("Commande inconnue. Utilisez 'create' ou 'send'.")


# --- Point d'entrée ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Utilisation : python mission_tool.py [create|send] nom_fichier.waypoints")
        sys.exit(1)
    action = sys.argv[1]
    fichier = sys.argv[2]
    if action == "create":
        create_mission(fichier)
    elif action == "send":
        send_mission(fichier)
    else:
        print("Commande inconnue. Utilisez 'create' ou 'send'.")