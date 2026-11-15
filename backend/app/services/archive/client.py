"""
Archive HTTP Client for querying SPHEREx TAP/SIA services.
"""
import requests
from app.config import TAP_URL, IBE_URL
from app.utils.logging_utils import get_logger

logger = get_logger("archive.client")

class ArchiveClient:
    def __init__(self, tap_url: str = TAP_URL, ibe_url: str = IBE_URL):
        self.tap_url = tap_url
        self.ibe_url = ibe_url

    def check_connection(self) -> bool:
        try:
            res = requests.get(f"{self.tap_url}/availability", timeout=5)
            return res.status_code == 200
        except Exception:
            return False

archive_client = ArchiveClient()
