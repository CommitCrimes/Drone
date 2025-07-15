import json
import sys
from pymavlink import mavutil
from get_flight_info import get_flight_info

import json
#Rajouter une premiere ligne pour le take off qui correspond a l'emplacement actuel du drone Faire une request Flight info pour récupérer la position
with open("config.json", "r") as f:
    config = json.load(f)

# Accéder aux valeurs
drone_id = config["drone_id"]

# ─────────────────────────────────────────────
# Fonction : create_mission
# But : Créer un fichier de mission QGroundControl (.waypoints)
# - En mode 'auto' : génère HOME et TAKEOFF, automatiquement, à partir de la position du drone. pas besoin de donner la commmand]
# - En mode 'man' : utilise les waypoints fournis sans rien ajouter
# Entrées :
#   - filename : chemin du fichier de sortie (.waypoints)
#   - altitude_takeoff : hauteur cible du décollage
#   - waypoints : liste de points fournis (optionnel)
#   - mode : "auto" ou "man"
# Sortie :
#   - Écrit le fichier .waypoints prêt à être envoyé
# ─────────────────────────────────────────────
def create_mission(filename, altitude_takeoff, waypoints=None, mode="auto"):
    mission_waypoints = []
    
    if mode == "man":
        if not waypoints:
            raise ValueError("En mode 'man', il faut passer la liste complète de waypoints.")
        mission_waypoints = waypoints

    else:
        flight_info = get_flight_info(drone_id)
        latitude = flight_info["latitude"]
        longitude = flight_info["longitude"]
        altitude = flight_info.get("altitude", altitude_takeoff)

        mission_waypoints.append({
            "seq": 0,
            "current": 1,
            "frame": 0,
            "command": 16,
            "param1": 0,
            "param2": 0,
            "param3": 0,
            "param4": 0,
            "lat": latitude,
            "lon": longitude,
            "alt": altitude,
            "autoContinue": 1
        })

        mission_waypoints.append({
            "seq": 1,
            "current": 0,
            "frame": 0,
            "command": 22,
            "param1": 0,
            "param2": 0,
            "param3": 0,
            "param4": 0,
            "lat": latitude,
            "lon": longitude,
            "alt": altitude_takeoff,
            "autoContinue": 1
        })

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

        if mission_waypoints:
            mission_waypoints[-1]["command"] = 21
            mission_waypoints[-1]["alt"] = 0

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

# ─────────────────────────────────────────────
# Fonction : send_mission
# But : Envoyer un fichier .waypoints vers le drone via MAVLink
# Étapes :
#   - Parse le fichier
#   - Envoie chaque point sur le lien MAVLink (UDP)
#   - Définit le point courant à 0
# ─────────────────────────────────────────────

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

def modify_mission(filename, seq_to_modify, updated_fields):
    """
    Modifie un waypoint dans un fichier .waypoints à partir de son numéro de séquence.

    :param filename: Chemin du fichier .waypoints
    :param seq_to_modify: Numéro de séquence (int) du waypoint à modifier
    :param updated_fields: Dictionnaire des champs à mettre à jour (ex: {"lat": 48.85, "lon": 2.29})
    """
    with open(filename, "r") as f:
        lines = f.readlines()

    if not lines or not lines[0].startswith("QGC WPL 110"):
        print("Format de fichier invalide.")
        return

    header = lines[0]
    waypoints = lines[1:]
    modified = False
    new_lines = [header]

    for line in waypoints:
        parts = line.strip().split("\t")
        if len(parts) != 12:
            new_lines.append(line)
            continue

        seq = int(parts[0])
        if seq == seq_to_modify:
            # Modifier les champs
            if "lat" in updated_fields:
                parts[8] = f"{float(updated_fields['lat']):.8f}"
            if "lon" in updated_fields:
                parts[9] = f"{float(updated_fields['lon']):.8f}"
            if "alt" in updated_fields:
                parts[10] = f"{float(updated_fields['alt']):.6f}"
            if "command" in updated_fields:
                parts[3] = str(int(updated_fields['command']))
            if "frame" in updated_fields:
                parts[2] = str(int(updated_fields['frame']))
            if "param1" in updated_fields:
                parts[4] = f"{float(updated_fields['param1']):.8f}"
            if "param2" in updated_fields:
                parts[5] = f"{float(updated_fields['param2']):.8f}"
            if "param3" in updated_fields:
                parts[6] = f"{float(updated_fields['param3']):.8f}"
            if "param4" in updated_fields:
                parts[7] = f"{float(updated_fields['param4']):.8f}"
            if "autoContinue" in updated_fields:
                parts[11] = str(int(updated_fields['autoContinue']))
            if "current" in updated_fields:
                parts[1] = str(int(updated_fields['current']))

            modified_line = "\t".join(parts) + "\n"
            new_lines.append(modified_line)
            modified = True
            print(f"Waypoint {seq} modifié.")
        else:
            new_lines.append(line)

    if not modified:
        print(f"Aucun waypoint avec seq={seq_to_modify} trouvé.")
        return

    with open(filename, "w") as f:
        f.writelines(new_lines)

    print(f"Fichier mis à jour : {filename}")


# --- Point d'entrée ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Utilisation : python mission_tool.py [create|send] mission.json/.waypoints")
        sys.exit(1)

    action = sys.argv[1]
    fichier = sys.argv[2]

    if action == "create":
        with open(fichier, "r") as f:
            data = json.load(f)

        output_filename = data.get("filename", "default_mission.waypoints")
        altitude = data.get("altitude_takeoff", 30)
        waypoints = data.get("waypoints", [])
        mode = data.get("mode", "auto")

        create_mission(output_filename, altitude, waypoints, mode)

    elif action == "send":
        send_mission(fichier)
    elif action == "modify":
        if len(sys.argv) < 5:
            print("Utilisation : python mission_tool.py modify fichier.waypoints seq champ=valeur ...")
            sys.exit(1)

        seq = int(sys.argv[3])
        updated_fields = {}
        for arg in sys.argv[4:]:
            if "=" in arg:
                key, val = arg.split("=")
                try:
                    updated_fields[key] = float(val) if "." in val else int(val)
                except ValueError:
                    updated_fields[key] = val

        modify_mission(fichier, seq, updated_fields)


    else:
        print("Commande inconnue. Utilisez 'create' ou 'send' ou 'modify'.")
