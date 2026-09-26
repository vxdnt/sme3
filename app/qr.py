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


def prune_expired_tokens() -> None:
    now = time.time()
    expired = [token for token, expires_at in list(state.active_tokens.items()) if expires_at <= now]
    for token in expired:
        del state.active_tokens[token]
    if state.current_token in expired:
        state.current_token = None
    if state.current_token is None and state.active_tokens:
        state.current_token = next(reversed(state.active_tokens))


def get_active_token_snapshot() -> dict:
    prune_expired_tokens()
    tokens = list(state.active_tokens.keys())
    current = state.current_token or (tokens[-1] if tokens else None)
    if current and current not in state.active_tokens:
        current = None
    return {
        "activeCount": len(tokens),
        "activeTokens": tokens,
        "currentToken": current,
    }


def is_token_valid(token: str | None) -> bool:
    if not token:
        return False
    prune_expired_tokens()
    expiry = state.active_tokens.get(token)
    return bool(expiry is not None and time.time() < expiry)


def rotate_token(base_url: str | None = None) -> dict:
    if base_url:
        state.current_base_url = base_url
    token = secrets.token_hex(16)
    expires_at = time.time() + ROTATE_SECONDS
    state.active_tokens[token] = expires_at
    state.current_token = token
    state.expires_at = expires_at
    scan_url = f"{state.current_base_url}/scan/{token}"
    payload = {
        "type": "token",
        "token": token,
        "expiresAt": expires_at,
        "qr": make_qr_data_uri(scan_url),
        "url": scan_url,
    }
    for queue in state.subscribers:
        queue.put_nowait(payload)
    return payload


def maybe_rotate_for_request(req_base: str) -> None:
    if req_base != state.current_base_url and "localhost" not in req_base and "127.0.0.1" not in req_base:
        rotate_token(req_base)
