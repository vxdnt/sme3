import asyncio, base64, io, logging, os, secrets, socket, sqlite3, time, json

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import qrcode
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope, Receive, Send
import uvicorn

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "").strip()
FROM_EMAIL: str = os.getenv("FROM_EMAIL", "tickets@resend.dev").strip()
ROTATE_SECONDS = 15

current_token: str | None = None
expires_at: float = 0.0
subscribers: list[asyncio.Queue] = []
current_base_url: str = ""


def _detect_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LAN_IP: str = _detect_lan_ip()
BASE_URL: str = f"http://{LAN_IP}:8000"

IS_POSTGRES = bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras


def get_pg_connection():
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def get_sqlite_connection():
    conn = sqlite3.connect("database.db", timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode lets readers (polling GET /api/attendees) and writers (POST /api/checkin)
    # proceed concurrently instead of blocking each other; busy_timeout makes any
    # remaining lock contention retry instead of failing immediately/silently.
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def init_db():
    """Initializes tables in PostgreSQL (Neon) or SQLite."""
    if IS_POSTGRES:
        try:
            conn = get_pg_connection()
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS attendees (
                            id          SERIAL PRIMARY KEY,
                            email       TEXT NOT NULL UNIQUE,
                            name        TEXT NOT NULL DEFAULT '',
                            quantity    INTEGER NOT NULL DEFAULT 1,
                            category    TEXT NOT NULL DEFAULT 'Male Stag',
                            ticket_sent BOOLEAN NOT NULL DEFAULT FALSE,
                            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                    """)
                    cur.execute("ALTER TABLE attendees ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'Male Stag';")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS check_ins (
                            id          SERIAL PRIMARY KEY,
                            email       TEXT NOT NULL,
                            scan_id     TEXT NOT NULL,
                            device_id   TEXT,
                            ip          TEXT,
                            device_type TEXT,
                            os          TEXT,
                            browser     TEXT,
                            scanned_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                    """)
            conn.close()
            print("[DB] Connected to Neon PostgreSQL and tables verified.")
        except Exception as e:
            print(f"[DB] Neon PostgreSQL initialization error: {e}")
    else:
        try:
            conn = get_sqlite_connection()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS attendees (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        email       TEXT NOT NULL UNIQUE,
                        name        TEXT NOT NULL DEFAULT '',
                        quantity    INTEGER NOT NULL DEFAULT 1,
                        category    TEXT NOT NULL DEFAULT 'Male Stag',
                        ticket_sent INTEGER NOT NULL DEFAULT 0,
                        created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                try:
                    conn.execute("ALTER TABLE attendees ADD COLUMN category TEXT NOT NULL DEFAULT 'Male Stag';")
                except Exception:
                    pass
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS check_ins (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        email       TEXT NOT NULL,
                        scan_id     TEXT NOT NULL,
                        device_id   TEXT,
                        ip          TEXT,
                        device_type TEXT,
                        os          TEXT,
                        browser     TEXT,
                        scanned_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            conn.close()
            print("[DB] Using local SQLite database (database.db).")
            print("     To switch to Neon DB, add DATABASE_URL=postgresql://... to .env")
        except Exception as e:
            print(f"[DB] SQLite initialization error: {e}")


def ensure_demo_attendee_exists():
    demo_email = 'attendee@example.com'
    attendee = db_get_attendee(demo_email)
    if not attendee:
        db_add_attendee(demo_email, 'Attendee', 1, 'Male Stag')
    elif not attendee.get('name'):
        db_add_attendee(demo_email, 'Attendee', attendee.get('quantity', 1), attendee.get('category', 'Male Stag'))


def db_add_attendee(email: str, name: str, quantity: int, category: str = "Male Stag"):
    email = email.lower().strip()
    name = name.strip()
    category = category.strip() or "Male Stag"
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO attendees (email, name, quantity, category)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (email) DO UPDATE
                            SET name = EXCLUDED.name,
                                quantity = EXCLUDED.quantity,
                                category = EXCLUDED.category
                        RETURNING email, name, quantity, category, ticket_sent, created_at;
                    """, (email, name, quantity, category))
                    return dict(cur.fetchone())
        finally:
            conn.close()
    else:
        conn = get_sqlite_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO attendees (email, name, quantity, category)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE
                        SET name = excluded.name,
                            quantity = excluded.quantity,
                            category = excluded.category;
                """, (email, name, quantity, category))
                cur = conn.execute("SELECT email, name, quantity, category, ticket_sent, created_at FROM attendees WHERE email = ?", (email,))
                row = cur.fetchone()
                return dict(row)
        finally:
            conn.close()


def db_list_attendees():
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            a.email,
                            a.name,
                            a.quantity,
                            a.category,
                            a.ticket_sent,
                            a.created_at,
                            COUNT(c.id) AS times_scanned,
                            MIN(c.scanned_at) AS first_scan,
                            MAX(c.scanned_at) AS last_scan
                        FROM attendees a
                        LEFT JOIN check_ins c ON LOWER(c.email) = LOWER(a.email)
                        GROUP BY a.email, a.name, a.quantity, a.category, a.ticket_sent, a.created_at
                        ORDER BY a.created_at ASC;
                    """)
                    rows = cur.fetchall()
                    result = []
                    for r in rows:
                        d = dict(r)
                        if d.get("first_scan"):
                            d["first_scan"] = str(d["first_scan"])
                        if d.get("last_scan"):
                            d["last_scan"] = str(d["last_scan"])
                        if d.get("created_at"):
                            d["created_at"] = str(d["created_at"])
                        result.append(d)
                    return result
        finally:
            conn.close()
    else:
        conn = get_sqlite_connection()
        try:
            with conn:
                cur = conn.execute("""
                    SELECT
                        a.email,
                        a.name,
                        a.quantity,
                        a.category,
                        a.ticket_sent,
                        a.created_at,
                        COUNT(c.id) AS times_scanned,
                        MIN(c.scanned_at) AS first_scan,
                        MAX(c.scanned_at) AS last_scan
                    FROM attendees a
                    LEFT JOIN check_ins c ON LOWER(c.email) = LOWER(a.email)
                    GROUP BY a.email, a.name, a.quantity, a.category, a.ticket_sent, a.created_at
                    ORDER BY a.created_at ASC;
                """)
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()


def db_get_attendee(email: str):
    email = email.lower().strip()
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            a.email,
                            a.name,
                            a.quantity,
                            a.category,
                            a.ticket_sent,
                            a.created_at,
                            COUNT(c.id) AS times_scanned,
                            MIN(c.scanned_at) AS first_scan,
                            MAX(c.scanned_at) AS last_scan
                        FROM attendees a
                        LEFT JOIN check_ins c ON LOWER(c.email) = LOWER(a.email)
                        WHERE LOWER(a.email) = %s
                        GROUP BY a.email, a.name, a.quantity, a.category, a.ticket_sent, a.created_at;
                    """, (email,))
                    row = cur.fetchone()
                    if not row:
                        return None
                    d = dict(row)
                    if d.get("first_scan"):
                        d["first_scan"] = str(d["first_scan"])
                    if d.get("last_scan"):
                        d["last_scan"] = str(d["last_scan"])
                    return d
        finally:
            conn.close()
    else:
        conn = get_sqlite_connection()
        try:
            with conn:
                cur = conn.execute("""
                    SELECT
                        a.email,
                        a.name,
                        a.quantity,
                        a.category,
                        a.ticket_sent,
                        a.created_at,
                        COUNT(c.id) AS times_scanned,
                        MIN(c.scanned_at) AS first_scan,
                        MAX(c.scanned_at) AS last_scan
                    FROM attendees a
                    LEFT JOIN check_ins c ON LOWER(c.email) = LOWER(a.email)
                    WHERE LOWER(a.email) = ?
                    GROUP BY a.email, a.name, a.quantity, a.category, a.ticket_sent, a.created_at;
                """, (email,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()


def db_record_checkin(email: str, scan_id: str, device_id: str, ip: str, device_type: str, os_name: str, browser: str, scanned_at: str):
    email = email.lower().strip()
    attendee = db_get_attendee(email) or {}
    attendee_name = (attendee.get('name') or email.split('@')[0].capitalize() or '').strip()
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM attendees WHERE LOWER(email) = %s;", (email,))
                    row = cur.fetchone()
                    if row and row.get('name'):
                        attendee_name = row['name']

                    cur.execute("SELECT COUNT(*) AS cnt, MAX(scanned_at) AS last FROM check_ins WHERE LOWER(email) = %s;", (email,))
                    stat = cur.fetchone()
                    times_scanned = stat["cnt"] if stat else 0
                    last_scan = str(stat["last"]) if (stat and stat["last"]) else None

                    cur.execute("""
                        INSERT INTO check_ins (email, scan_id, device_id, ip, device_type, os, browser, scanned_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW());
                    """, (email, scan_id, device_id, ip, device_type, os_name, browser))
                    return attendee_name, times_scanned, last_scan
        finally:
            conn.close()
    else:
        conn = get_sqlite_connection()
        try:
            with conn:
                cur = conn.execute("SELECT name FROM attendees WHERE LOWER(email) = ?;", (email,))
                row = cur.fetchone()
                if row and row["name"]:
                    attendee_name = row["name"]

                cur = conn.execute("SELECT COUNT(*) AS cnt, MAX(scanned_at) AS last FROM check_ins WHERE LOWER(email) = ?;", (email,))
                stat = cur.fetchone()
                times_scanned = stat["cnt"] if stat else 0
                last_scan = str(stat["last"]) if (stat and stat["last"]) else None

                conn.execute("""
                    INSERT INTO check_ins (email, scan_id, device_id, ip, device_type, os, browser, scanned_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (email, scan_id, device_id, ip, device_type, os_name, browser, scanned_at))
                return attendee_name, times_scanned, last_scan
        finally:
            conn.close()


def db_mark_ticket_sent(email: str):
    email = email.lower().strip()
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE attendees SET ticket_sent = TRUE WHERE LOWER(email) = %s;", (email,))
        finally:
            conn.close()
    else:
        conn = get_sqlite_connection()
        try:
            with conn:
                conn.execute("UPDATE attendees SET ticket_sent = 1 WHERE LOWER(email) = ?;", (email,))
        finally:
            conn.close()


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


def make_qr_data_uri(payload: str) -> str:
    img = qrcode.make(payload, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def rotate_token(base_url: str | None = None) -> dict:
    global current_token, expires_at, current_base_url
    if base_url:
        current_base_url = base_url
    current_token = secrets.token_hex(16)
    expires_at = time.time() + ROTATE_SECONDS
    scan_url = f"{current_base_url}/scan/{current_token}"
    payload = {
        "type": "token",
        "token": current_token,
        "expiresAt": expires_at,
        "qr": make_qr_data_uri(scan_url),
        "url": scan_url,
    }
    for q in subscribers:
        q.put_nowait(payload)
    return payload


async def rotation_loop():
    try:
        while True:
            await asyncio.sleep(ROTATE_SECONDS)
            rotate_token()
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n[*] LAN address: {BASE_URL}")
    print(f"    Website (SME Home): {BASE_URL}/")
    print(f"    Careers:            {BASE_URL}/careers")
    print(f"    Privacy:            {BASE_URL}/privacy")
    print(f"    Terms:              {BASE_URL}/terms")
    print(f"    Organizer Check-in: {BASE_URL}/checkin")
    print(f"    Dynamic QR Display: {BASE_URL}/generator")
    print(f"    Attendee Ticket:    {BASE_URL}/ticket?email=attendee@example.com&name=Attendee\n")
    init_db()
    ensure_demo_attendee_exists()
    rotate_token(BASE_URL)
    task = asyncio.create_task(rotation_loop())
    try:
        yield
    except asyncio.CancelledError:
        pass
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


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


class GracefulShutdownMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        try:
            await self.app(scope, receive, send)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass


app = FastAPI(lifespan=lifespan)
app.add_middleware(GracefulShutdownMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")

SME_DIR = Path("sme")


def get_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _is_local(base_url: str) -> bool:
    return "localhost" in base_url or "127.0.0.1" in base_url


def _to_json(d: dict) -> str:
    return json.dumps(d)


# ── SortMyEntries Website Routes ──

@app.get("/", response_class=HTMLResponse)
async def sme_home():
    return (SME_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/careers", response_class=HTMLResponse)
@app.get("/careers/", response_class=HTMLResponse)
async def sme_careers():
    return (SME_DIR / "careers" / "index.html").read_text(encoding="utf-8")


@app.get("/privacy", response_class=HTMLResponse)
@app.get("/privacy/", response_class=HTMLResponse)
async def sme_privacy():
    return (SME_DIR / "privacy" / "index.html").read_text(encoding="utf-8")


@app.get("/terms", response_class=HTMLResponse)
@app.get("/terms/", response_class=HTMLResponse)
async def sme_terms():
    return (SME_DIR / "terms" / "index.html").read_text(encoding="utf-8")


@app.get("/robots.txt")
async def robots_txt():
    return FileResponse(SME_DIR / "robots.txt", media_type="text/plain")


@app.get("/sitemap.xml")
async def sitemap_xml():
    return FileResponse(SME_DIR / "sitemap.xml", media_type="application/xml")


@app.get("/site.webmanifest")
async def site_manifest():
    return FileResponse(SME_DIR / "site.webmanifest", media_type="application/manifest+json")


@app.get("/favicon.ico")
async def favicon_ico():
    return FileResponse(SME_DIR / "favicon.ico")


@app.get("/favicon-16x16.png")
async def favicon_16():
    return FileResponse(SME_DIR / "favicon-16x16.png")


@app.get("/favicon-32x32.png")
async def favicon_32():
    return FileResponse(SME_DIR / "favicon-32x32.png")


@app.get("/apple-touch-icon.png")
async def apple_touch_icon():
    return FileResponse(SME_DIR / "apple-touch-icon.png")


@app.get("/android-chrome-192x192.png")
async def android_chrome_192():
    return FileResponse(SME_DIR / "android-chrome-192x192.png")


@app.get("/android-chrome-512x512.png")
async def android_chrome_512():
    return FileResponse(SME_DIR / "android-chrome-512x512.png")


@app.get("/CNAME")
async def cname():
    return FileResponse(SME_DIR / "CNAME", media_type="text/plain")


TEMPLATES_DIR = Path("templates")


def load_template(filename: str) -> str:
    path = TEMPLATES_DIR / filename
    if not path.exists():
        path = Path(filename)
    return path.read_text(encoding="utf-8")


def custom_404_html(message: str = "We couldn't find that page.") -> str:
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <meta name=\"robots\" content=\"noindex, nofollow\">
  <title>Page Not Found</title>
  <style>
    :root {{
      --black: #0a0a0a;
      --white: #ffffff;
      --gray-500: #6b7280;
      --accent: #e3544a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: var(--white);
      font-family: Arial, Helvetica, sans-serif;
      color: var(--black);
      text-align: center;
      padding: 24px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 2.4rem;
      color: var(--accent);
    }}
    p {{
      margin: 0 0 24px;
      color: var(--gray-500);
      font-size: 1rem;
    }}
    a {{
      text-decoration: none;
      color: var(--black);
      font-weight: 600;
      border-bottom: 2px solid var(--accent);
      padding-bottom: 2px;
    }}
  </style>
</head>
<body>
  <div>
    <h1>404</h1>
    <p>{message}</p>
    <a href=\"/\">Back to home</a>
  </div>
</body>
</html>
"""

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception(request: Request, exc: StarletteHTTPException):
    is_api = request.url.path.startswith("/api/")
    detail = getattr(exc, "detail", "An error occurred.")
    if exc.status_code == 404:
        if is_api:
            return JSONResponse({"ok": False, "error": detail}, status_code=404)
        accept = request.headers.get("accept", "")
        if "application/json" in accept.lower():
            return JSONResponse({"ok": False, "error": detail}, status_code=404)
        return HTMLResponse(custom_404_html("The page or API endpoint you requested doesn't exist."), status_code=404)
    if exc.status_code == 405:
        if is_api:
            return JSONResponse({"ok": False, "error": detail}, status_code=405)
        return HTMLResponse(custom_404_html("This action is not allowed for this URL."), status_code=405)
    if is_api:
        return JSONResponse({"ok": False, "error": detail}, status_code=exc.status_code)
    return JSONResponse({"detail": detail}, status_code=exc.status_code)


# ── Dynamic QR & Ticketing Routes ──

@app.get("/generator", response_class=HTMLResponse)
@app.get("/display", response_class=HTMLResponse)
async def generator_page(request: Request):
    global current_base_url
    req_base = get_base_url(request)
    if req_base != current_base_url and not _is_local(req_base):
        rotate_token(req_base)
    content = load_template("generator.html")
    return HTMLResponse(content, headers={"X-Robots-Tag": "noindex, nofollow"})


@app.get("/checkin", response_class=HTMLResponse)
async def legacy_checkin_page():
    return RedirectResponse(url="/check-in/big-fat-indian-scam-sangeet", status_code=307)


@app.get("/check-in", response_class=HTMLResponse)
@app.get("/check-in/", response_class=HTMLResponse)
async def checkin_page_root():
    return RedirectResponse(url="/check-in/big-fat-indian-scam-sangeet", status_code=307)


@app.get("/check-in/big-fat-indian-scam-sangeet", response_class=HTMLResponse)
async def checkin_page():
    content = load_template("check-in.html")
    return HTMLResponse(content, headers={"X-Robots-Tag": "noindex, nofollow"})


@app.get("/ticket", response_class=HTMLResponse)
async def ticket_page():
    content = load_template("ticket.html")
    return HTMLResponse(content, headers={"X-Robots-Tag": "noindex, nofollow"})


@app.get("/BFISS.jpg")
async def flyer_jpg():
    return FileResponse("static/BFISS.jpg")


@app.get("/BFISS2.png")
async def flyer_png():
    return FileResponse("static/BFISS2.png")


@app.get("/events")
async def events(request: Request):
    global current_base_url
    req_base = get_base_url(request)
    if req_base != current_base_url and not _is_local(req_base):
        rotate_token(req_base)

    queue: asyncio.Queue = asyncio.Queue()
    subscribers.append(queue)

    async def stream():
        try:
            yield f"data: {_to_json({'type': 'token', 'token': current_token, 'expiresAt': expires_at, 'qr': make_qr_data_uri(f'{current_base_url}/scan/{current_token}')})}\\n\\n"
            while True:
                payload = await queue.get()
                yield f"data: {_to_json(payload)}\\n\\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in subscribers:
                subscribers.remove(queue)

    return SafeStreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/qr")
async def qr_status(request: Request):
    global current_base_url
    req_base = get_base_url(request)
    if req_base != current_base_url and not _is_local(req_base):
        rotate_token(req_base)

    token_url = f"{current_base_url}/scan/{current_token}"
    payload = {
        "type": "token",
        "token": current_token,
        "expiresAt": expires_at,
        "qr": make_qr_data_uri(token_url),
        "url": token_url,
    }
    return JSONResponse(payload)


class AttendeeIn(BaseModel):
    email: str
    name: str = ""
    quantity: int = 1
    category: str = "Male Stag"
def send_ticket_email(to_email: str, name: str, ticket_url: str, quantity: int, category: str) -> dict:
    if not RESEND_API_KEY:
        return {"ok": False, "error": "RESEND_API_KEY not configured"}
    try:
        import resend as _resend
        _resend.api_key = RESEND_API_KEY
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your Ticket – Big Fat Indian Scam Sangeet</title>
<style>
  body {{ margin: 0; padding: 0; background: #f5f5f5; font-family: 'Google Sans', Arial, sans-serif; }}
  .wrap {{ max-width: 520px; margin: 32px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
  .hero {{ background: #0a0a0a; padding: 32px 28px 24px; color: #fff; }}
  .hero img {{ width: 100%; border-radius: 8px; margin-bottom: 20px; display: block; }}
  .hero h1 {{ margin: 0 0 6px; font-size: 1.4rem; font-weight: 600; }}
  .hero p {{ margin: 0; color: #9aa0a6; font-size: 0.88rem; }}
  .meta {{ display: flex; gap: 24px; margin-top: 18px; }}
  .meta-item {{ font-size: 0.8rem; }}
  .meta-label {{ color: #5f6368; text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.68rem; display: block; margin-bottom: 3px; }}
  .meta-value {{ color: #fff; }}
  .body {{ padding: 28px; }}
  .greeting {{ font-size: 1.05rem; font-weight: 500; color: #0a0a0a; margin: 0 0 8px; }}
  .subtext {{ font-size: 0.9rem; color: #5f6368; line-height: 1.6; margin: 0 0 24px; }}
  .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 0.88rem; }}
  .detail-label {{ color: #5f6368; }}
  .detail-value {{ font-weight: 500; color: #0a0a0a; }}
  .btn {{ display: block; margin: 28px auto 0; background: #e3544a; color: #fff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 0.95rem; text-align: center; max-width: 220px; }}
  .footer {{ text-align: center; padding: 20px 28px 28px; font-size: 0.78rem; color: #9aa0a6; line-height: 1.6; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <img src="{current_base_url}/BFISS.jpg" alt="Event Flyer">
    <h1>Big Fat Indian Scam Sangeet</h1>
    <p>Your ticket is confirmed!</p>
    <div class="meta">
      <div class="meta-item"><span class="meta-label">Date</span><span class="meta-value">27 Sep 2026</span></div>
      <div class="meta-item"><span class="meta-label">Time</span><span class="meta-value">6:00 PM</span></div>
      <div class="meta-item"><span class="meta-label">Venue</span><span class="meta-value">Eumsik Garden Restaurant</span></div>
    </div>
  </div>
  <div class="body">
    <p class="greeting">Hey {name}! 🎉</p>
    <p class="subtext">Your ticket for <strong>Big Fat Indian Scam Sangeet</strong> is confirmed. Present this ticket at the entrance and your organizer will scan you in.</p>
    <div class="detail-row"><span class="detail-label">Attendee</span><span class="detail-value">{name}</span></div>
    <div class="detail-row"><span class="detail-label">Category</span><span class="detail-value">{category}</span></div>
    <div class="detail-row"><span class="detail-label">Quantity</span><span class="detail-value">{quantity}</span></div>
    <div class="detail-row"><span class="detail-label">Date</span><span class="detail-value">27 Sep 2026 &middot; 6:00 PM</span></div>
    <div class="detail-row"><span class="detail-label">Venue</span><span class="detail-value">Eumsik Garden Restaurant</span></div>
    <a href="{ticket_url}" class="btn">Open My Ticket →</a>
  </div>
  <div class="footer">
    Open the link on your phone at the venue. The organizer's scanner will check you in instantly.<br>
    Questions? Reply to this email.
  </div>
</div>
</body>
</html>"""
        resp = _resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": "Your Ticket – Big Fat Indian Scam Sangeet 🎟️",
            "html": html_body,
        })
        return {"ok": True, "id": getattr(resp, "id", str(resp))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}




@app.post("/api/attendees")
async def add_attendee(body: AttendeeIn):
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Invalid email address.")
    try:
        attendee = db_add_attendee(body.email, body.name, max(1, body.quantity), body.category)
        ticket_url = f"{current_base_url}/ticket?email={attendee['email']}&name={attendee.get('name', '')}&qty={attendee.get('quantity', 1)}&cat={attendee.get('category', 'Male Stag')}"
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
        return {"ok": True, "attendee": attendee, "ticketUrl": ticket_url, "emailSent": email_result.get("ok", False), "emailError": email_result.get("error")}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


class ResendEmailIn(BaseModel):
    email: str


@app.post("/api/attendees/resend-email")
async def resend_attendee_email(body: ResendEmailIn):
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Invalid email address.")
    attendee = db_get_attendee(body.email)
    if not attendee:
        return JSONResponse({"ok": False, "error": "Attendee not found."}, status_code=404)
    ticket_url = f"{current_base_url}/ticket?email={attendee['email']}&name={attendee.get('name', '')}&qty={attendee.get('quantity', 1)}&cat={attendee.get('category', 'Male Stag')}"
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



@app.get("/api/attendees")
async def list_attendees():
    try:
        attendees = db_list_attendees()
        return {"ok": True, "attendees": attendees}
    except Exception as e:
        logging.getLogger("uvicorn.error").exception("Failed to list attendees")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/attendee")
async def get_attendee(email: str):
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    attendee = db_get_attendee(email)
    if not attendee:
        return JSONResponse({"ok": False, "error": "Attendee not found."}, status_code=404)
    return {"ok": True, "attendee": attendee}


class CheckInBody(BaseModel):
    token: str
    email: str


@app.post("/api/checkin")
async def api_checkin(body: CheckInBody, request: Request, response: Response):
    global current_base_url
    _scan_logger.info(f"[checkin] incoming request email={body.email!r} token={body.token[:8]}...")

    if body.token != current_token or time.time() >= expires_at:
        _scan_logger.info("[checkin] rejected: token invalid/expired")
        raise HTTPException(status_code=410, detail="QR code expired — please scan the latest code on display.")

    email = body.email.lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")

    try:
        ensure_demo_attendee_exists()
        attendee = db_get_attendee(email)
        if not attendee:
            _scan_logger.info(f"[checkin] rejected: {email} not registered")
            raise HTTPException(status_code=404, detail="This email is not registered for this event. Please use a valid attendee ticket.")

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

        existing = db_get_attendee(email)
        fallback_name = (body.email.split('@')[0].capitalize()) if body.email else 'Attendee'
        if not existing:
            db_add_attendee(email, name=fallback_name, quantity=1)
        elif not existing.get('name'):
            db_add_attendee(email, name=fallback_name, quantity=existing.get('quantity', 1), category=existing.get('category', 'Male Stag'))

        attendee_name, times_scanned, last_scan = db_record_checkin(
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

        attendee_display_name = attendee_name or (db_get_attendee(email) or {}).get('name') or email.split("@")[0].capitalize()

        event_payload: dict = {
            "type": "already_approved" if is_rescan else "approved",
            "scanId": scan_id,
            "deviceId": device_id,
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

        _scan_logger.info(f"[checkin] recorded ok: {email} timesScanned={times_scanned + 1} subscribers={len(subscribers)}")

        for q in subscribers:
            q.put_nowait(event_payload)

        _log_scan({**event_payload, "rescan": is_rescan})

        rotate_token(current_base_url)

        return {
            "ok": True,
            "name": attendee_display_name,
            "email": email,
            "scannedAt": scanned_at_display,
            "scannedAtRaw": scanned_at,
            "timesScanned": times_scanned + 1,
            "isRescan": is_rescan,
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger("uvicorn.error").exception(f"[checkin] failed for {email}")
        _scan_logger.info(f"[checkin] ERROR for {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Check-in failed on the server: {e}")


@app.get("/scan/{token}", response_class=HTMLResponse)
async def scan_redirect(token: str):
    valid = token == current_token and time.time() < expires_at
    if not valid:
        return HTMLResponse(
            render_result_page("Link Expired", """
            <div class="icon-circle fail-circle">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="#d93025" stroke-width="2.5" stroke-linecap="round"/>
              </svg>
            </div>
            <h1 class="title">Link Expired</h1>
            <p class="sub">This QR code has rotated.<br>Please scan the latest code on the display.</p>
            """),
            status_code=410,
            headers={"X-Robots-Tag": "noindex, nofollow"},
        )
    return HTMLResponse(
        f"""<!DOCTYPE html><html><head>
        <meta name="robots" content="noindex, nofollow">
        <meta http-equiv="refresh" content="0;url=/ticket?token={token}">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        </head><body><p style="font-family:sans-serif;text-align:center;margin-top:40px;">Opening ticket…</p></body></html>""",
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )


@app.get("/test-scan")
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
    for q in subscribers:
        q.put_nowait(payload)
    return {"ok": True, "payload": payload}


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


_scan_logger = logging.getLogger("scan")
_scan_logger.setLevel(logging.INFO)
_scan_handler = logging.FileHandler("scans.log", encoding="utf-8")
_scan_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_scan_logger.addHandler(_scan_handler)


def _log_scan(data: dict) -> None:
    _scan_logger.info(json.dumps(data, ensure_ascii=False))


def render_result_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="robots" content="noindex, nofollow">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Inter', system-ui, sans-serif; background: #0a0a0f; color: #fff;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }}
  .card {{ background: #13131c; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px;
          padding: 40px 32px; max-width: 360px; width: 100%; text-align: center; }}
  .icon-circle {{ width: 68px; height: 68px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; }}
  .fail-circle {{ background: rgba(239, 68, 68, 0.15); }}
  .title {{ font-size: 1.25rem; font-weight: 700; margin-bottom: 8px; }}
  .sub {{ font-size: 0.88rem; color: rgba(255,255,255,0.5); line-height: 1.6; }}
</style></head>
<body><div class="card">{body}</div></body></html>"""


if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except KeyboardInterrupt:
        pass