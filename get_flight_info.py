import math
from pymavlink import mavutil

def flight_info(drone_id, master):
    # Demande de flux de données pour la position
    master.mav.request_data_stream_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_POSITION,
        1, 1
    )

    heartbeat = master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
    msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)

    sys_status = master.recv_match(type='SYS_STATUS', blocking=False)
    if sys_status:
        voltage = sys_status.voltage_battery / 1000.0  # en volts
        current = sys_status.current_battery / 100.0   # en ampères
        battery_remaining = sys_status.battery_remaining  # en %
    else:
        voltage = None
        current = None
        battery_remaining = None

    if msg and heartbeat:
        vx = msg.vx / 100.0  # m/s
        vy = msg.vy / 100.0  # m/s
        vz = msg.vz / 100.0  # m/s

        return {
            "drone_id": str(drone_id),
            "is_armed": (heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0,
            "flight_mode": mavutil.mode_string_v10(heartbeat),
            "latitude": msg.lat / 1e7,
            "longitude": msg.lon / 1e7,
            "altitude_m": msg.relative_alt / 1000.0,
            "horizontal_speed_m_s": round(math.sqrt(vx**2 + vy**2), 2),
            "vertical_speed_m_s": round(vz, 2),
            "heading_deg": msg.hdg / 100.0,
            # "battery_voltage_V": voltage,
            # "battery_current_A": current,
            "battery_remaining_percent": battery_remaining
        }
    else:
        raise RuntimeError("Aucune donnée de position ou heartbeat reçue.")
