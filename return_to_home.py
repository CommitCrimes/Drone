from pymavlink import mavutil
import time

# Connexion MAVLink
print("Connexion au drone...")
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()
print(f"Connecté au système ID: {master.target_system}, composant ID: {master.target_component}")

def is_armed():
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
        0,
        mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT,
        0, 0, 0, 0, 0, 0
    )

    # Lire les messages jusqu'à HEARTBEAT
    while True:
        msg = master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
        if msg:
            return (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
        else:
            print("Pas de réponse au heartbeat.")
            return False

def set_mode(mode_name):
    mode_id = master.mode_mapping().get(mode_name.upper())
    if mode_id is None:
        print(f"[Erreur] Mode '{mode_name}' inconnu.")
        return
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )
    print(f"Passage en mode : {mode_name}")

# Vérifie si armé
if is_armed():
    print("Drone armé. Déclenchement du RTL.")
    set_mode("RTL")
else:
    print("Drone non armé. RTL annulé.")
