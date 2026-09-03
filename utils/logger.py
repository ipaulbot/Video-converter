import logging
from logging.handlers import RotatingFileHandler
import os
from utils.paths import get_data_dir

logger = logging.getLogger("VideoConverter")
logger.setLevel(logging.INFO)

# Centralised log folder under unified AppData\\NVC\\logs
log_dir = get_data_dir("logs")
log_file = os.path.join(log_dir, "conversion_log.txt")

file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)
