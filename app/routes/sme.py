from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.config import SME_DIR

router = APIRouter()


def _sme_file(*parts: str, media_type: str | None = None) -> FileResponse:
    path = SME_DIR.joinpath(*parts)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    if media_type:
        return FileResponse(path, media_type=media_type)
    return FileResponse(path)


def _sme_html(*parts: str) -> HTMLResponse:
    path = SME_DIR.joinpath(*parts)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page not found.")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/", response_class=HTMLResponse)
async def sme_home():
    return _sme_html("index.html")


@router.get("/careers", response_class=HTMLResponse)
@router.get("/careers/", response_class=HTMLResponse)
async def sme_careers():
    return _sme_html("careers", "index.html")


@router.get("/privacy", response_class=HTMLResponse)
@router.get("/privacy/", response_class=HTMLResponse)
async def sme_privacy():
    return _sme_html("privacy", "index.html")


@router.get("/terms", response_class=HTMLResponse)
@router.get("/terms/", response_class=HTMLResponse)
async def sme_terms():
    return _sme_html("terms", "index.html")


@router.get("/robots.txt")
async def robots_txt():
    return _sme_file("robots.txt", media_type="text/plain")


@router.get("/sitemap.xml")
async def sitemap_xml():
    return _sme_file("sitemap.xml", media_type="application/xml")


@router.get("/site.webmanifest")
async def site_manifest():
    return _sme_file("site.webmanifest", media_type="application/manifest+json")


@router.get("/favicon.ico")
async def favicon_ico():
    return _sme_file("favicon.ico")


@router.get("/favicon-16x16.png")
async def favicon_16():
    return _sme_file("favicon-16x16.png")


@router.get("/favicon-32x32.png")
async def favicon_32():
    return _sme_file("favicon-32x32.png")


@router.get("/apple-touch-icon.png")
async def apple_touch_icon():
    return _sme_file("apple-touch-icon.png")


@router.get("/android-chrome-192x192.png")
async def android_chrome_192():
    return _sme_file("android-chrome-192x192.png")


@router.get("/android-chrome-512x512.png")
async def android_chrome_512():
    return _sme_file("android-chrome-512x512.png")


@router.get("/CNAME")
async def cname():
    return _sme_file("CNAME", media_type="text/plain")
