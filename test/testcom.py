from pymavlink import mavutil

# Connexion
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')

# Attente du heartbeat initial
master.wait_heartbeat()
print("Connecté au système avec ID:", master.target_system)

last_mode = None

# Boucle d'écoute
while True:
    msg = master.recv_match(blocking=True)
    if not msg:
        continue

    msg_type = msg.get_type()

    # ➤ Détection de mode via HEARTBEAT
    if msg_type == "HEARTBEAT":
        custom_mode = msg.custom_mode
        mode = mavutil.mode_string_v10(msg)

        if mode != last_mode:
            print(f"🔄 Mode changé : {mode}")
            last_mode = mode

    # ➤ Messages système (PreArm, Arm, Disarm, etc.)
    if msg_type == "STATUSTEXT":
        severity = msg.severity
        text = msg.text

        print(f"[{severity}] {text}")

        if "PreArm" in text or "ARM" in text or "Disarm" in text:
            print("➡ Message lié à l’armement:", text)
