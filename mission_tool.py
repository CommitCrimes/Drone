import json
import sys
from pymavlink import mavutil

import json

def create_mission(filename, waypoints=None):
    default_waypoints = [
        {
            "command": 22,
            "param1": 0, "param2": 0, "param3": 0, "param4": 0,
            "lat": 0.0, "lon": 0.0, "alt": 10.0
        },
        {
            "command": 16,
            "param1": 0, "param2": 0, "param3": 0, "param4": 0,
            "lat": -35.3606711, "lon": 149.1649818, "alt": 100.0
        },
        {
            "command": 21,
            "param1": 0, "param2": 0, "param3": 0, "param4": 0,
            "lat": 0.0, "lon": 0.0, "alt": 0.0
        }
    ]

    wp_list = waypoints if waypoints else default_waypoints

    items = []
    for i, wp in enumerate(wp_list):
        items.append({
            "autoContinue": False,
            "command": wp["command"],
            "doJumpId": 0,
            "frame": 3,
            "params": [
                wp.get("param1", 0.0),
                wp.get("param2", 0.0),
                wp.get("param3", 0.0),
                wp.get("param4", 0.0),
                wp.get("lat", 0.0),
                wp.get("lon", 0.0),
                wp.get("alt", 0.0)
            ],
            "type": None,
            "TransectStyleComplexItem": None,
            "angle": None,
            "complexItemType": None,
            "entryLocation": None,
            "flyAlternateTransects": None,
            "polygon": None,
            "splitConcavePolygons": None,
            "version": None
        })

    mission_file = {
        "fileType": None,
        "geoFence": None,
        "groundStation": "MissionPlanner",
        "mission": {
            "cruiseSpeed": 0,
            "firmwareType": 0,
            "hoverSpeed": 0,
            "items": items,
            "plannedHomePosition": [
                wp_list[0].get("lat", 0.0),
                wp_list[0].get("lon", 0.0),
                wp_list[0].get("alt", 0.0)
            ],
            "vehicleType": 0,
            "version": 0
        },
        "rallyPoints": None,
        "version": 1
    }

    with open(filename, "w") as f:
        json.dump(mission_file, f, indent=2)
    print(f"Mission créée : {filename}")


def send_mission(filename):
    from pymavlink import mavutil
    import time

    master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
    master.wait_heartbeat()
    print(f"✅ Connecté à {master.target_system}/{master.target_component}")

    with open(filename, 'r') as f:
        data = json.load(f)

    waypoints = data["mission"]["items"]

    master.waypoint_clear_all_send()
    time.sleep(1)  # Petit délai

    master.waypoint_count_send(len(waypoints))
    print(f"📤 Envoi de {len(waypoints)} waypoints...")

    for i, wp in enumerate(waypoints):
        msg = master.recv_match(type='MISSION_REQUEST', blocking=True, timeout=10)
        if msg and msg.seq == i:
            p = wp["params"]
            master.mav.mission_item_send(
                master.target_system,
                master.target_component,
                i,
                wp.get("frame", mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT),
                wp["command"],
                0, 1,  # current=0, autocontinue=1
                p[0], p[1], p[2], p[3],
                p[4], p[5], p[6]
            )
            print(f"✅ WP {i} envoyé")
        else:
            print(f"⚠️ Pas de demande pour WP {i}")

    time.sleep(1)  # délai après envoi

    # Fixe le waypoint courant à 0
    master.mav.mission_set_current_send(master.target_system, master.target_component, 0)
    print("Waypoint courant défini à 0")

    time.sleep(1)

    # Passe en mode AUTO explicitement
    mode_id = master.mode_mapping().get('AUTO')
    if mode_id is None:
        print("⚠️ Mode AUTO non trouvé, vérifie le mode disponible")
    else:
        master.set_mode(mode_id)
        print("Mode changé en AUTO")

    time.sleep(2)

    # Envoi de la commande de démarrage de mission (optionnel)
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_MISSION_START,
        0,
        0,  # premier item
        0,  # dernier item (0 = tous)
        0, 0, 0, 0, 0
    )
    print("Mission activée (commande MAV_CMD_MISSION_START envoyée)")

    from pymavlink import mavutil
    import time

    # Connexion MAVLink
    master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
    master.wait_heartbeat()
    print(f"Connecté à {master.target_system}/{master.target_component}")

    # Charger la mission depuis fichier
    with open(filename, 'r') as f:
        data = json.load(f)

    waypoints = data["mission"]["items"]

    # Efface mission précédente
    master.waypoint_clear_all_send()

    # Envoie du nombre de waypoints
    master.waypoint_count_send(len(waypoints))
    print(f"📤 Envoi de {len(waypoints)} waypoints...")

    for i, wp in enumerate(waypoints):
        msg = master.recv_match(type='MISSION_REQUEST', blocking=True, timeout=5)
        if msg and msg.seq == i:
            p = wp["params"]
            master.mav.mission_item_send(
                master.target_system,
                master.target_component,
                i,
                wp.get("frame", mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT),
                wp["command"],
                0, 1,  # current, autocontinue
                p[0], p[1], p[2], p[3],
                p[4], p[5], p[6]
            )
            print(f"WP {i} envoyé")
        else:
            print(f"⚠️ Pas de demande pour WP {i}")

    print("Mission envoyée.")

    # Définir mission à l'index 0
    master.set_mode_auto()
    time.sleep(1)
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_MISSION_START,
        0,
        0,  # first item
        0,  # last item (0 = all)
        0, 0, 0, 0, 0
    )
    print("Mission activée (mode AUTO)")


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
