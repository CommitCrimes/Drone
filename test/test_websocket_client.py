import json
import time
import websocket
from pymavlink import mavutil

# Charger l'ID du drone
with open("../config.json") as f:
    config = json.load(f)
    drone_id = config.get("drone_id", 1)

# Connexion MAVLink
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()
print("MAVLink connecté")

# Connexion WebSocket (client)
ws = websocket.WebSocket()
try:
    ws.connect("ws://localhost:3000")
    time.sleep(1)
    print("Connecté au serveur WebSocket")

    def process_msg(msg):
        msg_type = msg.get_type()
        data = {"drone_id": drone_id}

        if msg_type == "HEARTBEAT":
            data.update({
                "type": "HEARTBEAT",
                "mode": mavutil.mode_string_v10(msg),
                "armed": bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            })
        elif msg_type == "GLOBAL_POSITION_INT":
            data.update({
                "type": "POSITION",
                "lat": msg.lat / 1e7,
                "lon": msg.lon / 1e7,
                "alt": msg.relative_alt / 1000.0,
                "heading": msg.hdg / 100.0 if msg.hdg != 65535 else None
            })
        elif msg_type == "VFR_HUD":
            data.update({
                "type": "VFR_HUD",
                "groundspeed": msg.groundspeed,
                "vspeed": msg.climb,
                "alt": msg.alt
            })
        else:
            return

        try:
            ws.send(json.dumps(data))
        except Exception as e:
            print("Erreur d’envoi WebSocket :", e)

    # Boucle principale
    while True:
        msg = master.recv_match(blocking=True)
        if msg:
            process_msg(msg)
        time.sleep(0.05)

except KeyboardInterrupt:
    print("Interruption manuelle")
    ws.close()

except Exception as e:
    print("Erreur principale :", e)
    ws.close()
