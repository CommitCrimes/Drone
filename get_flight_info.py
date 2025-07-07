import math
from pymavlink import mavutil

def get_flight_info():
    # Connexion MAVLink
    master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
    master.wait_heartbeat(timeout=5)

    # Demande d’état de position
    master.mav.request_data_stream_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_POSITION,
        1, 1  # fréquence et activation
    )

    # Attend le message GLOBAL_POSITION_INT
    msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)

    if msg:
        return {
            "latitude": msg.lat / 1e7,
            "longitude": msg.lon / 1e7,
            "altitude": msg.relative_alt / 1000,  # en mètres
            "ground_speed": round(math.sqrt(msg.vx**2 + msg.vy**2) / 100.0, 2)  # en m/s
        }
    else:
        raise RuntimeError("Aucune donnée de position reçue.")
