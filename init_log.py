import os
import logging
from datetime import datetime

# Date et heure actuelles
now = datetime.now()
date_str = now.strftime("%Y-%m-%d")     # ex: "2025-07-15"
time_str = now.strftime("%H-%M-%S")     # ex: "14-23-07"

# Dossier de logs/date
LOG_DIR = os.path.join("logs", date_str)

# Création du dossier s'il n'existe pas
os.makedirs(LOG_DIR, exist_ok=True)

# Fichier de log horodaté
log_filename = f"{time_str}.log"
log_path = os.path.join(LOG_DIR, log_filename)

# Configuration du logger
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)

# Logger réutilisable
logger = logging.getLogger("drone_logger")
