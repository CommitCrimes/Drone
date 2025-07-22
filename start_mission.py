from pymavlink import mavutil
import time

def start(master):
    # Connexion MAVLink
    print(f"Connecté au système ID: {master.target_system}, composant ID: {master.target_component}")

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

    # Passer en mode Loiter pour armer
    set_mode("Loiter")
    time.sleep(1)

    # Armer
    master.arducopter_arm()
    master.motors_armed_wait()
    print("Drone armé.")
    time.sleep(1)

    # Passer en mode AUTO
    set_mode("AUTO")
    time.sleep(3)

    # Lancer la mission
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_MISSION_START,
        0,   # Confirmation
        0,   # Première séquence à exécuter
        0,   # Dernière (0 = tous)
        0, 0, 0, 0, 0
    )

    print("Mission lancée.")

    # # Attente de la fin de mission (désarmement)
    # while True:
    #     msg = master.recv_match(type='HEARTBEAT', blocking=True)
    #     if not msg:
    #         continue

    #     armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
    #     mode = mavutil.mode_string_v10(msg)

    #     print(f"Mode: {mode} | Armé: {armed}")

    #     if not armed:
    #         print("Drone désarmé, fin de mission détectée.")
    #         break

    # # Notification vers ton backend
    # try:
    #     print("Notification envoyée. Code HTTP:")
    #     # import requests
    #     # response = requests.post("http://ton-api/mission-finished", json={"status": "done"})
    #     # print(response.status_code)
    # except Exception as e:
    #     print(f"Erreur lors de l’envoi de la notification : {e}")
