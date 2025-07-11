import socketio
import time
import math
from pymavlink import mavutil

# Adresse du serveur Socket.IO
SOCKETIO_URL = "http://localhost:6569"

# Initialisation du client Socket.IO
sio = socketio.Client()

@sio.event
def connect():
    print("Connecté au serveur Socket.IO")

@sio.event
def disconnect():
    print("Déconnecté du serveur Socket.IO")

# Fonction pour récupérer les données de vol du drone via MAVLink
def get_drone_status(drone_id):
    try:
        master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
        master.wait_heartbeat(timeout=5)

        heartbeat = master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)

        master.mav.request_data_stream_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_POSITION,
            1, 1
        )

        msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)

        if msg and heartbeat:
            vx = msg.vx / 100.0  # Vitesse horizontale x (m/s)
            vy = msg.vy / 100.0  # Vitesse horizontale y (m/s)
            vz = msg.vz / 100.0  # Vitesse verticale z (m/s)

            return {
                "drone_id": str(drone_id),
                "is_armed": (heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0,
                "flight_mode": mavutil.mode_string_v10(heartbeat),
                "latitude": msg.lat / 1e7,
                "longitude": msg.lon / 1e7,
                "altitude_m": round(msg.relative_alt / 1000.0, 2),
                "horizontal_speed_m_s": round(math.sqrt(vx**2 + vy**2), 2),
                "vertical_speed_m_s": round(vz, 2),
                "heading_deg": msg.hdg / 100.0
            }
        else:
            raise RuntimeError("Aucune donnée MAVLink reçue.")
    except Exception as e:
        print("Erreur MAVLink :", e)
        return None

# Boucle principale d'envoi des données du drone
try:
    print(f"Connexion à {SOCKETIO_URL}...")
    sio.connect(SOCKETIO_URL)

    while True:
        drone_status = get_drone_status(drone_id="drone_1")
        if drone_status:
            sio.emit("droneStatus", drone_status)
            print("Données envoyées :", drone_status)
        else:
            print("Aucune donnée à envoyer")

        time.sleep(1)

except KeyboardInterrupt:
    print("Arrêt manuel.")
    sio.disconnect()
