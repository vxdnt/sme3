from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.config import STATIC_DIR
from app.exceptions import load_frontend
from app.qr import maybe_rotate_for_request
from app.utils import get_base_url

router = APIRouter()
NOINDEX = {"X-Robots-Tag": "noindex, nofollow"}


def _html_page(filename: str) -> HTMLResponse:
    return HTMLResponse(load_frontend(filename), headers=NOINDEX)


def _image_response(filename: str) -> FileResponse:
    path = STATIC_DIR / "images" / filename
    if not path.exists():
        path = STATIC_DIR / filename
    return FileResponse(path)


@router.get("/generator", response_class=HTMLResponse)
@router.get("/display", response_class=HTMLResponse)
async def generator_page(request: Request):
    maybe_rotate_for_request(get_base_url(request))
    return _html_page("generator.html")


@router.get("/checkin", response_class=HTMLResponse)
async def legacy_checkin_page():
    return RedirectResponse(url="/check-in/big-fat-indian-scam-sangeet", status_code=307)


@router.get("/check-in", response_class=HTMLResponse)
@router.get("/check-in/", response_class=HTMLResponse)
async def checkin_page_root():
    return RedirectResponse(url="/check-in/big-fat-indian-scam-sangeet", status_code=307)


@router.get("/check-in/big-fat-indian-scam-sangeet", response_class=HTMLResponse)
async def checkin_page():
    return _html_page("check-in.html")


@router.get("/organizer/attendees", response_class=HTMLResponse)
async def organizer_attendees_page():
    return _html_page("attendees.html")


@router.get("/ticket", response_class=HTMLResponse)
async def ticket_page():
    return _html_page("ticket.html")


@router.get("/BFISS.jpg")
async def flyer_jpg():
    return _image_response("BFISS.jpg")


@router.get("/BFISS2.png")
async def flyer_png():
    return _image_response("BFISS2.png")
