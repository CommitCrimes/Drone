import threading
import queue
import time
from pymavlink import mavutil
from init_log import logger

# File de commandes (set_mode, etc.)
command_queue = queue.Queue()

# File de retour (réponse à une commande)
status_queue = queue.Queue()

# Dernières données de vol stockées ici
latest_telemetry = {}

# Connexion MAVLink
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()
logger.info("Heartbeat MAVLink reçu")

def mavlink_loop():
    global latest_telemetry
    while True:
        # Lecture des commandes en attente
        try:
            cmd = command_queue.get_nowait()

            if cmd["type"] == "set_mode":
                mode = cmd["mode"]
                mode_mapping = master.mode_mapping()

                if mode not in mode_mapping:
                    msg = f"Mode '{mode}' non supporté"
                    logger.warning(msg)
                    status_queue.put({"success": False, "message": msg})
                else:
                    mode_id = mode_mapping[mode]
                    master.set_mode(mode_id)
                    msg = f"Mode changé vers {mode} (ID: {mode_id})"
                    logger.info(msg)
                    status_queue.put({"success": True, "message": msg})

        except queue.Empty:
            pass

        # Lecture passive des infos MAVLink
        msg = master.recv_match(blocking=False)
        if msg:
            if msg.get_type() == "VFR_HUD":
                latest_telemetry["altitude"] = msg.alt
                latest_telemetry["airspeed"] = msg.airspeed
                latest_telemetry["groundspeed"] = msg.groundspeed
                latest_telemetry["heading"] = msg.heading
                latest_telemetry["throttle"] = msg.throttle

            elif msg.get_type() == "GLOBAL_POSITION_INT":
                latest_telemetry["lat"] = msg.lat / 1e7  # convertir en degrés
                latest_telemetry["lng"] = msg.lon / 1e7

            elif msg.get_type() == "SYS_STATUS":
                latest_telemetry["battery"] = msg.battery_remaining  # pourcentage

        time.sleep(0.1)

# Démarrage du thread MAVLink
threading.Thread(target=mavlink_loop, daemon=True).start()
