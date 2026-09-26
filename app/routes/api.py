import logging
import secrets
import time
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import state
from app.db import (
    db_add_attendee,
    db_get_attendee,
    db_list_attendees,
    db_mark_ticket_sent,
    db_mark_ticket_used,
    db_record_checkin,
    ensure_demo_attendee_exists,
)
from app.email_service import send_ticket_email
from app.qr import (
    get_active_token_snapshot,
    is_token_valid,
    make_qr_data_uri,
    maybe_rotate_for_request,
    rotate_token,
)
from app.security import create_signed_ticket_token, verify_signed_ticket_token
from app.utils import format_ist_datetime, get_base_url, log_scan, parse_user_agent, scan_log

router = APIRouter(prefix="/api")


class AttendeeIn(BaseModel):
    email: str
    name: str = ""
    quantity: int = 1
    category: str = "Male Stag"


class ResendEmailIn(BaseModel):
    email: str


class CheckInBody(BaseModel):
    token: str
    email: str = ""
    ticket_id: str = ""


def _ticket_url(attendee: dict) -> str:
    ticket_id = (attendee.get("ticket_id") or attendee.get("ticketId") or "").strip()
    if not ticket_id:
        return f"{state.current_base_url}/ticket"

    params = {
        "ticket_id": ticket_id,
        "token": create_signed_ticket_token(ticket_id),
    }
    return f"{state.current_base_url}/ticket?{urlencode(params)}"


@router.get("/qr")
async def qr_status(request: Request):
    maybe_rotate_for_request(get_base_url(request))
    session_id = (request.query_params.get("session_id") or "").strip() or None
    payload = rotate_token(state.current_base_url, session_id=session_id)
    snapshot = get_active_token_snapshot()
    payload["activeCount"] = snapshot["activeCount"]
    payload["activeTokens"] = snapshot["activeTokens"]
    payload["currentToken"] = snapshot["currentToken"]
    return JSONResponse(payload)


@router.post("/attendees")
async def add_attendee(body: AttendeeIn):
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Invalid email address.")
    try:
        attendee = db_add_attendee(body.email, body.name, max(1, body.quantity), body.category)
        ticket_url = _ticket_url(attendee)
        email_result = send_ticket_email(
            body.email,
            attendee.get("name", body.name),
            ticket_url,
            attendee.get("quantity", 1),
            attendee.get("category", "Male Stag"),
        )
        if email_result.get("ok"):
            db_mark_ticket_sent(attendee["email"])
            attendee["ticket_sent"] = True
        return {
            "ok": True,
            "attendee": attendee,
            "ticketUrl": ticket_url,
            "emailSent": email_result.get("ok", False),
            "emailError": email_result.get("error"),
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/attendees/resend-email")
async def resend_attendee_email(body: ResendEmailIn):
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Invalid email address.")
    attendee = db_get_attendee(body.email)
    if not attendee:
        return JSONResponse({"ok": False, "error": "Attendee not found."}, status_code=404)
    ticket_url = _ticket_url(attendee)
    email_result = send_ticket_email(
        attendee["email"],
        attendee.get("name", "") or "Guest",
        ticket_url,
        attendee.get("quantity", 1),
        attendee.get("category", "Male Stag"),
    )
    if email_result.get("ok"):
        db_mark_ticket_sent(attendee["email"])
    return {"ok": email_result.get("ok", False), "ticketUrl": ticket_url, "error": email_result.get("error")}


@router.get("/attendees")
async def list_attendees():
    try:
        attendees = db_list_attendees()
        return {"ok": True, "attendees": attendees}
    except Exception as e:
        logging.getLogger("uvicorn.error").exception("Failed to list attendees")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/attendee")
async def get_attendee(request: Request, email: str = None, ticket_id: str = None):
    key = (email or ticket_id or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Email or ticket ID is required.")

    token = (request.query_params.get("token") or "").strip()
    if ticket_id and token:
        try:
            payload = verify_signed_ticket_token(token)
            if payload.get("ticket_id") != ticket_id:
                raise ValueError("Ticket token mismatch.")
        except ValueError:
            return JSONResponse({"ok": False, "error": "Ticket link is invalid or expired."}, status_code=401)

    attendee = db_get_attendee(email=email) if email else db_get_attendee(ticket_id=ticket_id)
    if not attendee:
        return JSONResponse({"ok": False, "error": "Attendee not found."}, status_code=404)
    if ticket_id and attendee.get("used_at"):
        return JSONResponse({"ok": False, "error": "This ticket has already been used."}, status_code=410)
    return {"ok": True, "attendee": attendee}


@router.post("/checkin")
async def api_checkin(body: CheckInBody, request: Request, response: Response):
    ticket_id = (body.ticket_id or "").strip()
    email = (body.email or "").lower().strip() if body.email else ""
    scan_log(f"[checkin] incoming request ticket_id={ticket_id!r} email={email!r} token={body.token[:8]}...")

    if not is_token_valid(body.token):
        scan_log("[checkin] rejected: token invalid/expired")
        raise HTTPException(status_code=410, detail="QR code expired — please scan the latest code on display.")

    if not ticket_id and not email:
        raise HTTPException(status_code=400, detail="Ticket ID or email is required.")

    try:
        ensure_demo_attendee_exists()
        attendee = db_get_attendee(ticket_id=ticket_id) if ticket_id else db_get_attendee(email)
        if not attendee:
            scan_log(f"[checkin] rejected: ticket_id={ticket_id!r} email={email!r} not registered")
            raise HTTPException(
                status_code=404,
                detail="This ticket is not registered for this event. Please use a valid attendee ticket.",
            )

        if not email and attendee.get("email"):
            email = attendee["email"]

        if ticket_id and attendee.get("used_at"):
            raise HTTPException(status_code=410, detail="This ticket has already been used.")

        device_id = request.cookies.get("device_id")
        if not device_id:
            device_id = f"dev_{secrets.token_hex(6)}"
            response.set_cookie("device_id", device_id, max_age=60 * 60 * 24 * 365, httponly=True)

        ua = request.headers.get("user-agent", "Unknown")
        platform = request.headers.get("sec-ch-ua-platform", "").strip('"')
        language = request.headers.get("accept-language", "en").split(",")[0]
        forwarded = request.headers.get("x-forwarded-for")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "Unknown")
        parsed = parse_user_agent(ua, platform)

        scan_id = secrets.token_hex(4)
        scanned_at = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
        scanned_at_display = format_ist_datetime(scanned_at)

        existing = db_get_attendee(ticket_id=ticket_id) if ticket_id else db_get_attendee(email)
        fallback_name = (attendee.get("name") or (email.split("@")[0].capitalize() if email else "Attendee") or "Attendee").strip()
        if not existing:
            db_add_attendee(email or f"guest-{secrets.token_hex(4)}@example.invalid", name=fallback_name, quantity=1, ticket_id=ticket_id)
        elif not existing.get("name"):
            db_add_attendee(
                existing.get("email") or (email or f"guest-{secrets.token_hex(4)}@example.invalid"),
                name=fallback_name,
                quantity=existing.get("quantity", 1),
                category=existing.get("category", "Male Stag"),
                ticket_id=ticket_id or existing.get("ticket_id"),
            )

        attendee_name, times_scanned, last_scan = db_record_checkin(
            ticket_id=ticket_id or attendee.get("ticket_id") or "",
            email=email,
            scan_id=scan_id,
            device_id=device_id,
            ip=ip,
            device_type=parsed["deviceType"],
            os_name=parsed["os"],
            browser=parsed["browser"],
            scanned_at=scanned_at,
        )

        is_rescan = times_scanned > 0
        attendee_display_name = attendee_name or (db_get_attendee(ticket_id=ticket_id) if ticket_id else db_get_attendee(email) or {}).get("name") or (email.split("@")[0].capitalize() if email else "Attendee")

        event_payload: dict = {
            "type": "already_approved" if is_rescan else "approved",
            "scanId": scan_id,
            "deviceId": device_id,
            "ticketId": ticket_id or attendee.get("ticket_id") or "",
            "email": email,
            "name": attendee_display_name,
            "ip": ip,
            "deviceType": parsed["deviceType"],
            "os": parsed["os"],
            "browser": parsed["browser"],
            "userAgent": ua,
            "language": language,
            "approvedAt": scanned_at_display,
            "approvedAtRaw": scanned_at,
            "timesScanned": times_scanned + 1,
        }
        if is_rescan:
            event_payload["lastScan"] = format_ist_datetime(last_scan) if last_scan else scanned_at_display
            event_payload["newScan"] = scanned_at_display

        scan_log(f"[checkin] recorded ok: ticket_id={ticket_id or attendee.get('ticket_id')!r} timesScanned={times_scanned + 1} subscribers={len(state.subscribers)}")

        for queue in state.subscribers:
            queue.put_nowait(event_payload)

        db_mark_ticket_used(ticket_id or attendee.get("ticket_id") or "")
        log_scan({**event_payload, "rescan": is_rescan})
        rotate_token(state.current_base_url)

        return {
            "ok": True,
            "name": attendee_display_name,
            "email": email,
            "ticketId": ticket_id or attendee.get("ticket_id") or "",
            "scannedAt": scanned_at_display,
            "scannedAtRaw": scanned_at,
            "timesScanned": times_scanned + 1,
            "isRescan": is_rescan,
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger("uvicorn.error").exception(f"[checkin] failed for ticket_id={ticket_id!r} email={email!r}")
        scan_log(f"[checkin] ERROR for ticket_id={ticket_id!r} email={email!r}: {e}")
        raise HTTPException(status_code=500, detail=f"Check-in failed on the server: {e}")
