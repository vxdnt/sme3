import asyncio
import secrets
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.types import Receive, Scope, Send

from app import state
from app.exceptions import load_frontend
from app.qr import make_qr_data_uri, maybe_rotate_for_request, rotate_token
from app.utils import get_base_url, to_json

router = APIRouter()
NOINDEX = {"X-Robots-Tag": "noindex, nofollow"}


class SafeStreamingResponse(StreamingResponse):
    async def listen_for_disconnect(self, receive: Receive) -> None:
        try:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    break
        except (asyncio.CancelledError, Exception):
            pass

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass


@router.get("/events")
async def events(request: Request):
    maybe_rotate_for_request(get_base_url(request))
    session_id = (request.query_params.get("session_id") or "").strip() or "default"

    queue: asyncio.Queue = asyncio.Queue()
    state.subscribers.append(queue)
    state.session_subscribers.setdefault(session_id, []).append(queue)

    async def stream():
        try:
            token = state.session_tokens.get(session_id) or state.current_token or next(reversed(state.active_tokens), None)
            if token:
                token_url = f"{state.current_base_url}/scan/{token}"
                payload = {
                    "type": "token",
                    "token": token,
                    "expiresAt": state.active_tokens.get(token, state.expires_at),
                    "qr": make_qr_data_uri(token_url),
                }
            else:
                payload = rotate_token(state.current_base_url, session_id=session_id)
            yield f"data: {to_json(payload)}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {to_json(event)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in state.subscribers:
                state.subscribers.remove(queue)
            if queue in state.session_subscribers.get(session_id, []):
                state.session_subscribers[session_id].remove(queue)
            if not state.session_subscribers.get(session_id):
                state.session_subscribers.pop(session_id, None)

    return SafeStreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/scan/{token}", response_class=HTMLResponse)
async def scan_redirect(token: str):
    valid = bool(token in state.active_tokens and time.time() < state.active_tokens[token])
    if not valid:
        return HTMLResponse(load_frontend("expired.html"), status_code=410, headers=NOINDEX)
    return HTMLResponse(
        f"""<!DOCTYPE html><html><head>
        <meta name="robots" content="noindex, nofollow">
        <meta http-equiv="refresh" content="0;url=/ticket?token={token}">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        </head><body><p style="font-family:sans-serif;text-align:center;margin-top:40px;">Opening ticket…</p></body></html>""",
        headers=NOINDEX,
    )


@router.get("/test-scan")
async def test_scan():
    payload = {
        "type": "approved",
        "scanId": secrets.token_hex(4),
        "deviceId": f"dev_{secrets.token_hex(6)}",
        "email": "priya.sharma@example.com",
        "name": "Priya Sharma",
        "ip": "192.168.1.42",
        "deviceType": "Mobile Phone",
        "os": "Android",
        "browser": "Google Chrome",
        "userAgent": "Mozilla/5.0 (Linux; Android 14) Chrome/120 Mobile",
        "language": "en-IN",
        "approvedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "timesScanned": 1,
    }
    for queue in state.subscribers:
        queue.put_nowait(payload)
    return {"ok": True, "payload": payload}
