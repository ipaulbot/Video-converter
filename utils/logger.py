import logging
import os
from logging.handlers import RotatingFileHandler

from utils.paths import get_data_dir

logger = logging.getLogger("VideoConverter")

# Default INFO. Set NVC_LOG_LEVEL=DEBUG to surface the suppressed-error
# tracebacks that best-effort handlers throughout the app record at debug
# level -- that is the first thing to try when diagnosing a silent failure.
_LEVEL_NAME = (os.environ.get("NVC_LOG_LEVEL") or "INFO").strip().upper()
logger.setLevel(getattr(logging, _LEVEL_NAME, logging.INFO))

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
