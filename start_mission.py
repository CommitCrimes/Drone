from pymavlink import mavutil
import time

master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()
print(f"Connecté au système ID: {master.target_system}, composant ID: {master.target_component}")



landed = False

def set_mode(mode_name):
    mode_id = master.mode_mapping().get(mode_name.upper())
    if mode_id is None:
        print(f"Mode {mode_name} inconnu.")
        return
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )
    print(f"Mode demandé: {mode_name} (id: {mode_id})")

# Passer en mode AUTO
set_mode("Loiter")
time.sleep(1)
# Armer le drone
master.arducopter_arm()
master.motors_armed_wait()
print("Drone armé.")
time.sleep(1)
set_mode("AUTO")
time.sleep(3)
# 4. Envoyer la commande MAV_CMD_MISSION_START
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_MISSION_START,
    0,   # Confirmation
    0,   # Première séquence à exécuter (point 0)
    0,   # Dernière (0 = tous)
    0, 0, 0, 0, 0  # paramètres inutilisés
)

time.sleep(1)

# Attente du désarmement
print("Attente de la fin de la mission et de l’atterrissage...")

drone_desarme = False

while not drone_desarme:
    msg = master.recv_match(type='HEARTBEAT', blocking=True)
    if not msg:
        continue

    armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
    mode = mavutil.mode_string_v10(msg)

    print(f"Mode: {mode} | Armé: {armed}")

    # Vérifie si le drone est désarmé (=> mission probablement terminée)
    if not armed:
        print("Drone désarmé, fin de mission détectée.")
        drone_desarme = True

# Envoie d’un POST à ton API une fois le drone désarmé
try:
    print(f"Notification envoyée. Code HTTP:")
except Exception as e:
    print(f"Erreur lors de l’envoi de la notification : {e}")




# Si une mission est chargée, elle démarre automatiquement
