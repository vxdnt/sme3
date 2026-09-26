import os
import socket
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STATIC_DIR = ROOT_DIR / "static"
SME_DIR = ROOT_DIR / "sme"

DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "").strip()
BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "").strip()
FROM_EMAIL: str = os.getenv("FROM_EMAIL", "tickets@resend.dev").strip()
MAIL_DEFAULT_SENDER: str = os.getenv("MAIL_DEFAULT_SENDER", FROM_EMAIL).strip()
MAIL_REPLY_TO: str = os.getenv("MAIL_REPLY_TO", FROM_EMAIL).strip()
ROTATE_SECONDS = 15
TICKET_TTL_SECONDS = int(os.getenv("TICKET_TTL_SECONDS", "86400"))
TICKET_SECRET = os.getenv("TICKET_SECRET", "change-this-ticket-secret-in-production").strip()
SQLITE_PATH = ROOT_DIR / "database.db"

IS_POSTGRES = bool(
    DATABASE_URL
    and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"))
)


def detect_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LAN_IP: str = detect_lan_ip()
BASE_URL: str = f"http://{LAN_IP}:8000"
APP_BASE_URL: str = os.getenv("APP_BASE_URL", BASE_URL).strip()
