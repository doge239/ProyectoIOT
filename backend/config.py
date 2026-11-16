import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "backend" / ".env")


class Settings:
    def __init__(self):
        self.production = os.getenv("ENVIRONMENT", "development") == "production"
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'parking.db'}")
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.admin_username = os.getenv("ADMIN_USERNAME", "admin")
        self.admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH", "")
        self.device_keys = json.loads(os.getenv("DEVICE_KEYS", "{}"))
        if not isinstance(self.device_keys, dict) or any(
            not isinstance(key, str) or len(key) < 24 or not isinstance(slots, list)
            or not slots or any(slot not in ("A1", "A2", "A3", "A4") for slot in slots)
            for key, slots in self.device_keys.items()
        ):
            raise RuntimeError("DEVICE_KEYS requiere claves de al menos 24 caracteres y listas de puestos A1–A4.")
        self.allow_anonymous = os.getenv("ALLOW_ANONYMOUS_TELEMETRY", "false").lower() == "true"
        self.origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip()]
        self.session_hours = int(os.getenv("SESSION_HOURS", "8"))
        if not 1 <= self.session_hours <= 24:
            raise RuntimeError("SESSION_HOURS debe estar entre 1 y 24.")
        if not self.admin_password_hash:
            raise RuntimeError("Configura ADMIN_PASSWORD_HASH. Para uso local: python -m backend.configure")
        if self.production and (self.allow_anonymous or not self.device_keys or self.database_url.startswith("sqlite")):
            raise RuntimeError("Producción requiere PostgreSQL, DEVICE_KEYS y telemetría autenticada.")
