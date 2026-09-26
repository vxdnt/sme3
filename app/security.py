import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config import TICKET_SECRET, TICKET_TTL_SECONDS


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not value:
        return b""
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + pad).encode("ascii"))


def create_signed_ticket_token(ticket_id: str, ttl_seconds: int = TICKET_TTL_SECONDS) -> str:
    ticket_id = (ticket_id or "").strip()
    if not ticket_id:
        raise ValueError("Ticket ID is required.")

    payload = {
        "ticket_id": ticket_id,
        "exp": int(time.time()) + ttl_seconds,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(TICKET_SECRET.encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).digest()
    return f"{_b64url_encode(payload_json.encode('utf-8'))}.{_b64url_encode(signature)}"


def verify_signed_ticket_token(token: str) -> dict[str, Any]:
    try:
        if not token:
            raise ValueError("Missing ticket token.")

        payload_b64, sig_b64 = token.split(".", 1)
        payload_json = _b64url_decode(payload_b64).decode("utf-8")
        expected_sig = hmac.new(TICKET_SECRET.encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(actual_sig, expected_sig):
            raise ValueError("Invalid signature.")

        payload = json.loads(payload_json)
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Ticket has expired.")
        return payload
    except Exception as exc:  # pragma: no cover - verification path only
        raise ValueError(str(exc)) from exc
