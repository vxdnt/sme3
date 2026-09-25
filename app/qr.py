import base64
import io
import secrets
import time

import qrcode

from app import state
from app.config import ROTATE_SECONDS


def make_qr_data_uri(payload: str) -> str:
    img = qrcode.make(payload, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def rotate_token(base_url: str | None = None) -> dict:
    if base_url:
        state.current_base_url = base_url
    state.current_token = secrets.token_hex(16)
    state.expires_at = time.time() + ROTATE_SECONDS
    scan_url = f"{state.current_base_url}/scan/{state.current_token}"
    payload = {
        "type": "token",
        "token": state.current_token,
        "expiresAt": state.expires_at,
        "qr": make_qr_data_uri(scan_url),
        "url": scan_url,
    }
    for queue in state.subscribers:
        queue.put_nowait(payload)
    return payload


def maybe_rotate_for_request(req_base: str) -> None:
    if req_base != state.current_base_url and "localhost" not in req_base and "127.0.0.1" not in req_base:
        rotate_token(req_base)
