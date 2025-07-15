from pymavlink import mavutil
import time

# Connexion MAVLink
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()
print(f"Connecté au système ID: {master.target_system}, composant ID: {master.target_component}")

def set_mode(mode_name):
    mode_id = master.mode_mapping().get(mode_name.upper())
    if mode_id is None:
        print(f"Mode {mode_name} inconnu.")
        return False

    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )
    print(f"Mode demandé : {mode_name} (id: {mode_id})")
    return True
time.sleep(1)

# Étape 1 : Passer en mode LAND
if not set_mode("LAND"):
    print("Impossible de passer en mode LAND.")
    exit(1)

# Étape 2 : Surveiller l'état jusqu'à ce que le drone soit désarmé
print("Atterrissage en cours...")

while True:
    msg = master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
    if not msg:
        continue

    armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
    mode = mavutil.mode_string_v10(msg)

    print(f"Mode actuel: {mode} | Armé: {armed}")
    
    if not armed:
        print("Drone désarmé. Atterrissage terminé.")
        break

    time.sleep(2)
