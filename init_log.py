import os
import logging
from datetime import datetime

# Préparer dossier et fichier
now = datetime.now()
year_str = now.strftime("%Y")
day_str = now.strftime("%m-%d")
LOG_DIR = os.path.join("logs", year_str)
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = f"{day_str}.log"
log_path = os.path.join(LOG_DIR, log_filename)

# Formatter commun
formatter = logging.Formatter('%(asctime)s — %(levelname)s — %(message)s', datefmt='%H:%M:%S')

# Handler fichier
file_handler = logging.FileHandler(log_path, mode='a')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Logger principal (application)
logger = logging.getLogger("drone_logger")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

# Logger HTTP Flask (werkzeug)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)
werkzeug_logger.addHandler(file_handler)
werkzeug_logger.propagate = False  # pour éviter les doublons
