import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Request

from app.config import ROOT_DIR

_scan_logger = logging.getLogger("scan")
_scan_logger.setLevel(logging.INFO)
if not _scan_logger.handlers:
    _scan_handler = logging.FileHandler(ROOT_DIR / "scans.log", encoding="utf-8")
    _scan_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    _scan_logger.addHandler(_scan_handler)


def get_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def is_local(base_url: str) -> bool:
    return "localhost" in base_url or "127.0.0.1" in base_url


def to_json(payload: dict) -> str:
    return json.dumps(payload)


def format_ist_datetime(value: str | datetime | None) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            if "T" not in raw and " " in raw:
                raw = raw.replace(" ", "T", 1)
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return dt.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %H:%M:%S")


def parse_user_agent(ua: str, platform_header: str = "") -> dict:
    ua_lower = ua.lower()

    if "iphone" in ua_lower:
        os_name, device_type = "iOS (iPhone)", "Mobile Phone"
    elif "ipad" in ua_lower:
        os_name, device_type = "iOS (iPad)", "Tablet"
    elif "android" in ua_lower:
        os_name, device_type = "Android", ("Mobile Phone" if "mobile" in ua_lower else "Tablet")
    elif "windows" in ua_lower:
        os_name, device_type = "Windows", "Desktop"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        os_name, device_type = "macOS", "Desktop"
    elif "linux" in ua_lower:
        os_name, device_type = "Linux", "Desktop"
    elif platform_header:
        os_name, device_type = platform_header, "Device"
    else:
        os_name, device_type = "Unknown OS", "Unknown Device"

    if "edg" in ua_lower:
        browser = "Microsoft Edge"
    elif "crios" in ua_lower:
        browser = "Chrome (iOS)"
    elif "chrome" in ua_lower:
        browser = "Google Chrome"
    elif "safari" in ua_lower:
        browser = "Apple Safari"
    elif "firefox" in ua_lower or "fxios" in ua_lower:
        browser = "Mozilla Firefox"
    elif "opera" in ua_lower or "opr" in ua_lower:
        browser = "Opera"
    else:
        browser = "Browser"

    return {"os": os_name, "deviceType": device_type, "browser": browser}


def log_scan(data: dict) -> None:
    _scan_logger.info(json.dumps(data, ensure_ascii=False))


def scan_log(message: str) -> None:
    _scan_logger.info(message)
