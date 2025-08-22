from doctest import master
import json
import os
import sys
from pymavlink import mavutil
from get_flight_info import flight_info
import time
from typing import List, Dict, Any
import threading
from telemetry import MAVLINK_IO_LOCK  # même verrou que la télémétrie


import json

# ─────────────────────────────────────────────
# Fonction : create_mission
# But : Créer un fichier de mission QGroundControl (.waypoints)
# - En mode 'auto' : génère HOME et TAKEOFF, automatiquement, à partir de la position du drone. pas besoin de donner la commmand]
# - En mode 'man' : utilise les waypoints fournis sans rien ajouter
# Entrées :
#   - filename : chemin du fichier de sortie (.waypoints)
#   - altitude_takeoff : hauteur cible du décollage
#   - waypoints : liste de points fournis (optionnel)
#   - mode : "auto" ou "man"
# Sortie :
#   - Écrit le fichier .waypoints prêt à être envoyé
# ─────────────────────────────────────────────
def create_mission(
    master,
    filename,
    altitude_takeoff,
    waypoints=None,
    mode="auto",
    startlat=None,
    startlon=None,
    startalt=None,
    drone_id=None,
):
    mission_waypoints = []

    if mode == "man":
        if not waypoints:
            raise ValueError("En mode 'man', il faut passer la liste complète de waypoints.")
        mission_waypoints = waypoints
    else:
        if startlat is not None and startlon is not None:
            latitude  = float(startlat)
            longitude = float(startlon)
            altitude0 = float(startalt) if startalt is not None else float(altitude_takeoff)
        else:
            with MAVLINK_IO_LOCK:
                info = flight_info(drone_id if drone_id is not None else 0, master)
            latitude  = float(info["latitude"])
            longitude = float(info["longitude"])
            # compat: selon ta fonction flight_info, la clé peut être altitude_m
            altitude0 = float(info.get("altitude_m", info.get("altitude", altitude_takeoff)))

        # WP 0 : point de départ (WAYPOINT)
        mission_waypoints.append({
            "seq": 0,
            "current": 1,
            "frame": 0,
            "command": 16,
            "param1": 0, "param2": 0, "param3": 0, "param4": 0,
            "lat": latitude, "lon": longitude, "alt": altitude0,
            "autoContinue": 1
        })

        # WP 1 : TAKEOFF vers altitude_takeoff
        mission_waypoints.append({
            "seq": 1,
            "current": 0,
            "frame": 0,
            "command": 22,
            "param1": 0, "param2": 0, "param3": 0, "param4": 0,
            "lat": latitude, "lon": longitude, "alt": float(altitude_takeoff),
            "autoContinue": 1
        })

        # WPs utilisateur (dès seq=2)
        if waypoints:
            for i, wp in enumerate(waypoints, start=2):
                mission_waypoints.append({
                    "seq": i,
                    "current": 0,
                    "frame": wp.get("frame", 3),
                    "command": wp.get("command", 16),
                    "param1": wp.get("param1", 0.0),
                    "param2": wp.get("param2", 0.0),
                    "param3": wp.get("param3", 0.0),
                    "param4": wp.get("param4", 0.0),
                    "lat": wp.get("lat", 0.0),
                    "lon": wp.get("lon", 0.0),
                    "alt": wp.get("alt", 100.0),
                    "autoContinue": wp.get("autoContinue", 1)
                })

        # Dernier WP → LAND
        if mission_waypoints:
            mission_waypoints[-1]["command"] = 21
            mission_waypoints[-1]["alt"] = 0

    # Écriture du fichier (assure-toi que le dossier existe)
    outdir = "missions"
    os.makedirs(outdir, exist_ok=True)
    outpath = filename if os.path.isabs(filename) else os.path.join(outdir, filename)

    with open(outpath, "w") as f:
        f.write("QGC WPL 110\n")
        for wp in mission_waypoints:
            line = (
                f"{wp['seq']}\t{wp['current']}\t{wp['frame']}\t{wp['command']}\t"
                f"{float(wp['param1']):.8f}\t{float(wp['param2']):.8f}\t{float(wp['param3']):.8f}\t{float(wp['param4']):.8f}\t"
                f"{float(wp['lat']):.8f}\t{float(wp['lon']):.8f}\t{float(wp['alt']):.6f}\t{wp['autoContinue']}\n"
            )
            f.write(line)

    print(f"Mission .waypoints créée : {outpath}")
    return outpath

# ─────────────────────────────────────────────
# Fonction : send_mission
# But : Envoyer un fichier .waypoints vers le drone via MAVLink
# Étapes :
#   - Parse le fichier
#   - Envoie chaque point sur le lien MAVLink (UDP)
#   - Définit le point courant à 0
# ─────────────────────────────────────────────

def send_mission(
    filename: str,
    master,
    *,
    count_timeout: float = 2.0,
    item_timeout: float = 2.0,
    max_silence_retries: int = 3
) -> None:
    """
    Envoie un fichier .waypoints avec verrou exclusif MAVLink.
    - draine les messages
    - clear + count
    - répond aux MISSION_REQUEST(_INT) avec l'item demandé
    - attend un MISSION_ACK en fin de transfert
    - set current = 0
    """

    if master is None:
        raise ValueError("master est requis")

    # Lire/parse le fichier .waypoints
    with open(filename, "r") as f:
        lines = f.readlines()
    if not lines or not lines[0].startswith("QGC WPL 110"):
        raise RuntimeError("Format .waypoints invalide (header manquant).")

    waypoints: List[Dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.strip().split("\t")
        if len(parts) != 12:
            continue
        waypoints.append({
            "seq": int(parts[0]),
            "current": int(parts[1]),
            "frame": int(parts[2]),
            "command": int(parts[3]),
            "param1": float(parts[4]),
            "param2": float(parts[5]),
            "param3": float(parts[6]),
            "param4": float(parts[7]),
            "lat": float(parts[8]),
            "lon": float(parts[9]),
            "alt": float(parts[10]),
            "autoContinue": int(parts[11]),
        })

    n = len(waypoints)
    if n == 0:
        raise RuntimeError("Aucun waypoint à envoyer.")

    print(f"[mission] Envoi de {n} waypoints depuis {filename}")

    with MAVLINK_IO_LOCK:
        # 0) Nettoyer d’éventuels messages en attente
        _drain_mav(master, 0.2)

        # 1) Clear ancien plan
        master.waypoint_clear_all_send()
        time.sleep(0.1)

        # 2) Envoyer le COUNT
        master.waypoint_count_send(n)

        # 3) Boucle jusqu’à ce que tous les items soient demandés
        sent = set()
        silence_retries = 0

        while len(sent) < n:
            msg = master.recv_match(
                type=['MISSION_REQUEST_INT', 'MISSION_REQUEST'],
                blocking=True,
                timeout=item_timeout
            )

            if msg is None:
                # L’autopilote n’a rien demandé — on renvoie COUNT pour relancer
                silence_retries += 1
                if silence_retries > max_silence_retries:
                    raise RuntimeError("Pas de MISSION_REQUEST reçu (timeout).")
                print("[mission] Silence → renvoi du COUNT")
                master.waypoint_count_send(n)
                continue

            # Dès qu’on reçoit quelque chose, on reset le compteur de silence
            silence_retries = 0

            req_type = msg.get_type()
            req_seq = int(getattr(msg, "seq", -1))
            if req_seq < 0 or req_seq >= n:
                print(f"[mission] Requête seq hors bornes ({req_seq}) ignorée.")
                continue

            wp = waypoints[req_seq]

            if req_type == 'MISSION_REQUEST_INT':
                master.mav.mission_item_int_send(
                    master.target_system,
                    master.target_component,
                    req_seq,
                    wp["frame"],
                    wp["command"],
                    wp["current"],
                    wp["autoContinue"],
                    float(wp["param1"]),
                    float(wp["param2"]),
                    float(wp["param3"]),
                    float(wp["param4"]),
                    int(wp["lat"] * 1e7),
                    int(wp["lon"] * 1e7),
                    float(wp["alt"]),
                )
            else:
                # Version float classique
                master.mav.mission_item_send(
                    master.target_system,
                    master.target_component,
                    req_seq,
                    wp["frame"],
                    wp["command"],
                    wp["current"],
                    wp["autoContinue"],
                    float(wp["param1"]),
                    float(wp["param2"]),
                    float(wp["param3"]),
                    float(wp["param4"]),
                    float(wp["lat"]),
                    float(wp["lon"]),
                    float(wp["alt"]),
                )

            sent.add(req_seq)
            print(f"[mission] WP {req_seq} envoyé ({req_type})")

        # 4) Attendre l’ACK de fin de transfert
        ack = master.recv_match(type='MISSION_ACK', blocking=True, timeout=count_timeout)
        if not ack:
            raise RuntimeError("MISSION_ACK non reçu (timeout).")
        print(f"[mission] ACK reçu: {getattr(ack, 'type', 'UNKNOWN')}")

        # 5) Définir le waypoint courant à 0
        master.mav.mission_set_current_send(master.target_system, master.target_component, 0)
        print("[mission] Waypoint courant défini à 0 → Mission envoyée.")

    # Définit le waypoint courant à 0
    master.mav.mission_set_current_send(master.target_system, master.target_component, 0)
    print("Waypoint courant défini à 0")

    time.sleep(1)
    print("Mission envoyé")

def modify_mission(filename, seq_to_modify, updated_fields):
    """
    Modifie un waypoint dans un fichier .waypoints à partir de son numéro de séquence.

    :param filename: Chemin du fichier .waypoints
    :param seq_to_modify: Numéro de séquence (int) du waypoint à modifier
    :param updated_fields: Dictionnaire des champs à mettre à jour (ex: {"lat": 48.85, "lon": 2.29})
    """
    with open(filename, "r") as f:
        lines = f.readlines()

    if not lines or not lines[0].startswith("QGC WPL 110"):
        print("Format de fichier invalide.")
        return

    header = lines[0]
    waypoints = lines[1:]
    modified = False
    new_lines = [header]

    for line in waypoints:
        parts = line.strip().split("\t")
        if len(parts) != 12:
            new_lines.append(line)
            continue

        seq = int(parts[0])
        if seq == seq_to_modify:
            # Modifier les champs
            if "lat" in updated_fields:
                parts[8] = f"{float(updated_fields['lat']):.8f}"
            if "lon" in updated_fields:
                parts[9] = f"{float(updated_fields['lon']):.8f}"
            if "alt" in updated_fields:
                parts[10] = f"{float(updated_fields['alt']):.6f}"
            if "command" in updated_fields:
                parts[3] = str(int(updated_fields['command']))
            if "frame" in updated_fields:
                parts[2] = str(int(updated_fields['frame']))
            if "param1" in updated_fields:
                parts[4] = f"{float(updated_fields['param1']):.8f}"
            if "param2" in updated_fields:
                parts[5] = f"{float(updated_fields['param2']):.8f}"
            if "param3" in updated_fields:
                parts[6] = f"{float(updated_fields['param3']):.8f}"
            if "param4" in updated_fields:
                parts[7] = f"{float(updated_fields['param4']):.8f}"
            if "autoContinue" in updated_fields:
                parts[11] = str(int(updated_fields['autoContinue']))
            if "current" in updated_fields:
                parts[1] = str(int(updated_fields['current']))

            modified_line = "\t".join(parts) + "\n"
            new_lines.append(modified_line)
            modified = True
            print(f"Waypoint {seq} modifié.")
        else:
            new_lines.append(line)

    if not modified:
        print(f"Aucun waypoint avec seq={seq_to_modify} trouvé.")
        return

    with open(filename, "w") as f:
        f.writelines(new_lines)

    print(f"Fichier mis à jour : {filename}")

def _drain_mav(master, duration=0.2):
    t0 = time.time()
    while time.time() - t0 < duration:
        msg = master.recv_match(blocking=False, timeout=0)
        if msg is None:
            break

def download_mission(master, timeout: float = 2.0, retries: int = 3) -> List[Dict[str, Any]]:
    """
    Télécharge de façon robuste la mission chargée:
      - verrou exclusif MAVLink
      - drain du pipe
      - requêtes avec retries
      - vérification du seq
      - MISSION_ACK en fin de transfert
    """
    with MAVLINK_IO_LOCK:
        # Nettoyer d'éventuels vieux messages
        _drain_mav(master, 0.2)

        # 1) Demander la liste
        for attempt in range(retries):
            master.mav.mission_request_list_send(master.target_system, master.target_component)
            count_msg = master.recv_match(type='MISSION_COUNT', blocking=True, timeout=timeout)
            if count_msg:
                break
        if not count_msg:
            raise RuntimeError("MISSION_COUNT non reçu (timeout).")

        count = int(count_msg.count)
        items: List[Dict[str, Any]] = [None] * count  # type: ignore

        # 2) Demander chaque item avec retries et vérif du seq
        for i in range(count):
            got = False
            for attempt in range(retries):
                # Demande INT d'abord
                master.mav.mission_request_int_send(master.target_system, master.target_component, i)
                msg = master.recv_match(type=['MISSION_ITEM_INT', 'MISSION_ITEM'], blocking=True, timeout=timeout)

                if msg is None:
                    # Fallback: demande non-INT
                    master.mav.mission_request_send(master.target_system, master.target_component, i)
                    msg = master.recv_match(type=['MISSION_ITEM', 'MISSION_ITEM_INT'], blocking=True, timeout=timeout)

                if msg is None:
                    continue  # retry

                seq = int(getattr(msg, "seq", i))
                if seq != i:
                    # message hors ordre -> on réessaye (ou on range à l'index reçu si tu préfères)
                    continue

                if msg.get_type() == 'MISSION_ITEM_INT':
                    lat = float(msg.x) / 1e7
                    lon = float(msg.y) / 1e7
                    alt = float(msg.z)
                else:
                    lat = float(msg.x)
                    lon = float(msg.y)
                    alt = float(msg.z)

                items[i] = {
                    "seq": seq,
                    "current": int(getattr(msg, "current", 0)),
                    "frame": int(getattr(msg, "frame", 0)),
                    "command": int(getattr(msg, "command", 16)),
                    "param1": float(getattr(msg, "param1", 0.0)),
                    "param2": float(getattr(msg, "param2", 0.0)),
                    "param3": float(getattr(msg, "param3", 0.0)),
                    "param4": float(getattr(msg, "param4", 0.0)),
                    "lat": lat,
                    "lon": lon,
                    "alt": alt,
                    "autoContinue": int(getattr(msg, "autocontinue", 1)),
                }
                got = True
                break

            if not got:
                raise RuntimeError(f"Item {i}: pas de réponse MISSION_ITEM(_INT).")

        # 3) ACK en fin de transfert (important pour finir la session mission)
        master.mav.mission_ack_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_MISSION_ACCEPTED,
            0
        )

        return [it for it in items if it is not None]

# --- Point d'entrée ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Utilisation : python mission_tool.py [create|send] mission.json/.waypoints")
        sys.exit(1)

    action = sys.argv[1]
    fichier = sys.argv[2]

    if action == "create":
        with open(fichier, "r") as f:
            data = json.load(f)

        output_filename = data.get("filename", "default_mission.waypoints")
        altitude = data.get("altitude_takeoff", 30)
        waypoints = data.get("waypoints", [])
        mode = data.get("mode", "auto")

        create_mission(output_filename, altitude, waypoints, mode)

    elif action == "send":
        send_mission(fichier)
    elif action == "modify":
        if len(sys.argv) < 5:
            print("Utilisation : python mission_tool.py modify fichier.waypoints seq champ=valeur ...")
            sys.exit(1)

        seq = int(sys.argv[3])
        updated_fields = {}
        for arg in sys.argv[4:]:
            if "=" in arg:
                key, val = arg.split("=")
                try:
                    updated_fields[key] = float(val) if "." in val else int(val)
                except ValueError:
                    updated_fields[key] = val

        modify_mission(fichier, seq, updated_fields)
    elif action == "download":
        # Nécessite que tu aies ajouté download_mission() plus haut
        from mission_tool import download_mission  # si la fonction est dans ce même fichier tu peux enlever cet import

        outfile = sys.argv[2]
        items = download_mission(master)

        if outfile.endswith(".waypoints"):
            os.makedirs(os.path.dirname(outfile) or "missions", exist_ok=True)
            outpath = outfile
            if not os.path.isabs(outpath):
                if not outpath.startswith("missions" + os.sep) and not outpath.startswith("missions/"):
                    outpath = os.path.join("missions", outpath)
            with open(outpath, "w") as f:
                f.write("QGC WPL 110\n")
                for i, wp in enumerate(items):
                    line = (
                        f"{wp.get('seq', i)}\t{wp.get('current', 0)}\t{wp.get('frame', 0)}\t{wp.get('command', 16)}\t"
                        f"{float(wp.get('param1', 0.0)):.8f}\t{float(wp.get('param2', 0.0)):.8f}\t"
                        f"{float(wp.get('param3', 0.0)):.8f}\t{float(wp.get('param4', 0.0)):.8f}\t"
                        f"{float(wp.get('lat', 0.0)):.8f}\t{float(wp.get('lon', 0.0)):.8f}\t"
                        f"{float(wp.get('alt', 0.0)):.6f}\t{int(wp.get('autoContinue', 1))}\n"
                    )
                    f.write(line)
            print(f"Mission téléchargée → {outpath}")


    else:
        print("Commande inconnue. Utilisez 'create' ou 'send' ou 'modify'.")

