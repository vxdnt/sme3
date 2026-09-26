import secrets
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import DATABASE_URL, IS_POSTGRES, SQLITE_PATH

if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras


def get_pg_connection():
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def get_sqlite_connection():
    conn = sqlite3.connect(str(SQLITE_PATH), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def ensure_ticket_id_columns():
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("ALTER TABLE attendees ADD COLUMN IF NOT EXISTS ticket_id TEXT;")
                    cur.execute("ALTER TABLE attendees ADD COLUMN IF NOT EXISTS used_at TIMESTAMPTZ;")
                    cur.execute("ALTER TABLE check_ins ADD COLUMN IF NOT EXISTS ticket_id TEXT;")
                    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_attendees_ticket_id ON attendees (ticket_id) WHERE ticket_id IS NOT NULL;")
        finally:
            conn.close()
        return

    conn = get_sqlite_connection()
    try:
        with conn:
            try:
                conn.execute("ALTER TABLE attendees ADD COLUMN ticket_id TEXT NOT NULL UNIQUE DEFAULT '';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE check_ins ADD COLUMN ticket_id TEXT NOT NULL DEFAULT '';")
            except Exception:
                pass
    finally:
        conn.close()


def generate_ticket_id() -> str:
    ensure_ticket_id_columns()
    while True:
        prefix = secrets.randbelow(9990 - 1110 + 1) + 1110
        suffix = secrets.token_urlsafe(28)
        ticket_id = f"{prefix}/{suffix}"
        existing = None
        try:
            if IS_POSTGRES:
                conn = get_pg_connection()
                try:
                    with conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1 FROM attendees WHERE ticket_id = %s;", (ticket_id,))
                            existing = cur.fetchone()
                finally:
                    conn.close()
            else:
                conn = get_sqlite_connection()
                try:
                    with conn:
                        existing = conn.execute("SELECT 1 FROM attendees WHERE ticket_id = ?;", (ticket_id,)).fetchone()
                finally:
                    conn.close()
        except Exception:
            existing = None
        if not existing:
            return ticket_id


def init_db():
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
                            ticket_id   TEXT NOT NULL UNIQUE DEFAULT '',
                            ticket_sent BOOLEAN NOT NULL DEFAULT FALSE,
                            used_at     TIMESTAMPTZ,
                            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                    """)
                    cur.execute(
                        "ALTER TABLE attendees ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'Male Stag';"
                    )
                    cur.execute(
                        "ALTER TABLE attendees ADD COLUMN IF NOT EXISTS ticket_id TEXT UNIQUE;"
                    )
                    cur.execute("ALTER TABLE attendees ADD COLUMN IF NOT EXISTS used_at TIMESTAMPTZ;")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS check_ins (
                            id          SERIAL PRIMARY KEY,
                            email       TEXT NOT NULL,
                            ticket_id   TEXT NOT NULL,
                            scan_id     TEXT NOT NULL,
                            device_id   TEXT,
                            ip          TEXT,
                            device_type TEXT,
                            os          TEXT,
                            browser     TEXT,
                            scanned_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                    """)
                    cur.execute(
                        "ALTER TABLE check_ins ADD COLUMN IF NOT EXISTS ticket_id TEXT;"
                    )
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
                        ticket_id   TEXT NOT NULL UNIQUE DEFAULT '',
                        ticket_sent INTEGER NOT NULL DEFAULT 0,
                        used_at     TEXT,
                        created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                try:
                    conn.execute("ALTER TABLE attendees ADD COLUMN category TEXT NOT NULL DEFAULT 'Male Stag';")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE attendees ADD COLUMN ticket_id TEXT NOT NULL UNIQUE DEFAULT '';")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE attendees ADD COLUMN used_at TEXT;")
                except Exception:
                    pass
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS check_ins (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        email       TEXT NOT NULL,
                        ticket_id   TEXT NOT NULL,
                        scan_id     TEXT NOT NULL,
                        device_id   TEXT,
                        ip          TEXT,
                        device_type TEXT,
                        os          TEXT,
                        browser     TEXT,
                        scanned_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                try:
                    conn.execute("ALTER TABLE check_ins ADD COLUMN ticket_id TEXT NOT NULL DEFAULT '';")
                except Exception:
                    pass
            conn.close()
            print("[DB] Using local SQLite database (database.db).")
            print("     To switch to Neon DB, add DATABASE_URL=postgresql://... to .env")
        except Exception as e:
            print(f"[DB] SQLite initialization error: {e}")


def db_add_attendee(email: str, name: str, quantity: int, category: str = "Male Stag", ticket_id: str | None = None):
    ensure_ticket_id_columns()
    email = email.lower().strip()
    name = name.strip()
    category = category.strip() or "Male Stag"
    ticket_id = (ticket_id or generate_ticket_id()).strip()
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO attendees (email, name, quantity, category, ticket_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (email) DO UPDATE
                            SET name = EXCLUDED.name,
                                quantity = EXCLUDED.quantity,
                                category = EXCLUDED.category,
                                ticket_id = COALESCE(attendees.ticket_id, EXCLUDED.ticket_id),
                                used_at = NULL
                        RETURNING email, name, quantity, category, ticket_id, ticket_sent, used_at, created_at;
                    """, (email, name, quantity, category, ticket_id))
                    return dict(cur.fetchone())
        finally:
            conn.close()

    conn = get_sqlite_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO attendees (email, name, quantity, category, ticket_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE
                    SET name = excluded.name,
                        quantity = excluded.quantity,
                        category = excluded.category,
                        ticket_id = COALESCE(ticket_id, excluded.ticket_id),
                        used_at = NULL;
            """, (email, name, quantity, category, ticket_id))
            cur = conn.execute(
                "SELECT email, name, quantity, category, ticket_id, ticket_sent, used_at, created_at FROM attendees WHERE email = ?",
                (email,),
            )
            return dict(cur.fetchone())
    finally:
        conn.close()


def db_list_attendees():
    query = """
        SELECT
            a.email,
            a.name,
            a.quantity,
            a.category,
            a.ticket_id,
            a.ticket_sent,
            a.used_at,
            a.created_at,
            COUNT(c.id) AS times_scanned,
            MIN(c.scanned_at) AS first_scan,
            MAX(c.scanned_at) AS last_scan
        FROM attendees a
        LEFT JOIN check_ins c ON LOWER(COALESCE(c.email, '')) = LOWER(a.email) OR c.ticket_id = a.ticket_id
        GROUP BY a.email, a.name, a.quantity, a.category, a.ticket_id, a.ticket_sent, a.used_at, a.created_at
        ORDER BY a.created_at ASC;
    """
    for _ in range(2):
        try:
            if IS_POSTGRES:
                conn = get_pg_connection()
                try:
                    with conn:
                        with conn.cursor() as cur:
                            cur.execute(query)
                            result = []
                            for r in cur.fetchall():
                                d = dict(r)
                                for key in ("first_scan", "last_scan", "created_at", "used_at"):
                                    if d.get(key):
                                        d[key] = str(d[key])
                                result.append(d)
                            return result
                finally:
                    conn.close()

            conn = get_sqlite_connection()
            try:
                with conn:
                    return [dict(r) for r in conn.execute(query).fetchall()]
            finally:
                conn.close()
        except Exception:
            ensure_ticket_id_columns()
            continue
    return []


def db_get_attendee(email: str = None, ticket_id: str = None):
    ensure_ticket_id_columns()
    if email:
        email = email.lower().strip()
    ticket_id = (ticket_id or "").strip()
    if not email and not ticket_id:
        return None

    query = """
        SELECT
            a.email,
            a.name,
            a.quantity,
            a.category,
            a.ticket_id,
            a.ticket_sent,
            a.used_at,
            a.created_at,
            COUNT(c.id) AS times_scanned,
            MIN(c.scanned_at) AS first_scan,
            MAX(c.scanned_at) AS last_scan
        FROM attendees a
        LEFT JOIN check_ins c ON LOWER(COALESCE(c.email, '')) = LOWER(a.email) OR c.ticket_id = a.ticket_id
        WHERE {where_clause}
        GROUP BY a.email, a.name, a.quantity, a.category, a.ticket_id, a.ticket_sent, a.used_at, a.created_at;
    """

    for _ in range(2):
        try:
            if IS_POSTGRES:
                conn = get_pg_connection()
                try:
                    with conn:
                        with conn.cursor() as cur:
                            if ticket_id:
                                cur.execute(query.format(where_clause="a.ticket_id = %s"), (ticket_id,))
                            else:
                                cur.execute(query.format(where_clause="LOWER(a.email) = %s"), (email,))
                            row = cur.fetchone()
                            if not row:
                                return None
                            d = dict(row)
                            if d.get("first_scan"):
                                d["first_scan"] = str(d["first_scan"])
                            if d.get("last_scan"):
                                d["last_scan"] = str(d["last_scan"])
                            if d.get("used_at"):
                                d["used_at"] = str(d["used_at"])
                            return d
                finally:
                    conn.close()

            conn = get_sqlite_connection()
            try:
                with conn:
                    if ticket_id:
                        row = conn.execute(query.format(where_clause="a.ticket_id = ?"), (ticket_id,)).fetchone()
                    else:
                        row = conn.execute(query.format(where_clause="LOWER(a.email) = ?"), (email,)).fetchone()
                    return dict(row) if row else None
            finally:
                conn.close()
        except Exception:
            ensure_ticket_id_columns()
            continue
    return None


def db_get_attendee_by_ticket_id(ticket_id: str):
    return db_get_attendee(ticket_id=ticket_id)


def db_record_checkin(ticket_id: str, email: str, scan_id: str, device_id: str, ip: str, device_type: str, os_name: str, browser: str, scanned_at: str):
    email = email.lower().strip() if email else ""
    ticket_id = (ticket_id or "").strip()
    attendee = db_get_attendee(ticket_id=ticket_id) or (db_get_attendee(email=email) if email else {})
    attendee_name = (attendee.get("name") or (email.split("@")[0].capitalize() if email else "Guest") or "Guest").strip()
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name, email FROM attendees WHERE ticket_id = %s OR LOWER(email) = %s LIMIT 1;", (ticket_id, email or ""))
                    row = cur.fetchone()
                    if row and row.get("name"):
                        attendee_name = row["name"]
                        if row.get("email"):
                            email = row["email"]

                    cur.execute(
                        "SELECT COUNT(*) AS cnt, MAX(scanned_at) AS last FROM check_ins WHERE ticket_id = %s OR LOWER(email) = %s;",
                        (ticket_id, email or ""),
                    )
                    stat = cur.fetchone()
                    times_scanned = stat["cnt"] if stat else 0
                    last_scan = str(stat["last"]) if (stat and stat["last"]) else None

                    cur.execute("""
                        INSERT INTO check_ins (email, ticket_id, scan_id, device_id, ip, device_type, os, browser, scanned_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """, (email, ticket_id, scan_id, device_id, ip, device_type, os_name, browser))
                    return attendee_name, times_scanned, last_scan
        finally:
            conn.close()

    conn = get_sqlite_connection()
    try:
        with conn:
            row = conn.execute("SELECT name, email FROM attendees WHERE ticket_id = ? OR LOWER(email) = ? LIMIT 1;", (ticket_id, email or "")).fetchone()
            if row and row["name"]:
                attendee_name = row["name"]
                if row["email"]:
                    email = row["email"]

            stat = conn.execute(
                "SELECT COUNT(*) AS cnt, MAX(scanned_at) AS last FROM check_ins WHERE ticket_id = ? OR LOWER(email) = ?;",
                (ticket_id, email or ""),
            ).fetchone()
            times_scanned = stat["cnt"] if stat else 0
            last_scan = str(stat["last"]) if (stat and stat["last"]) else None

            conn.execute("""
                INSERT INTO check_ins (email, ticket_id, scan_id, device_id, ip, device_type, os, browser, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (email, ticket_id, scan_id, device_id, ip, device_type, os_name, browser, scanned_at))
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
        return

    conn = get_sqlite_connection()
    try:
        with conn:
            conn.execute("UPDATE attendees SET ticket_sent = 1 WHERE LOWER(email) = ?;", (email,))
    finally:
        conn.close()


def db_mark_ticket_used(ticket_id: str):
    ticket_id = (ticket_id or "").strip()
    if not ticket_id:
        return
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE attendees SET used_at = NOW() WHERE ticket_id = %s;", (ticket_id,))
        finally:
            conn.close()
        return

    conn = get_sqlite_connection()
    try:
        with conn:
            conn.execute("UPDATE attendees SET used_at = ? WHERE ticket_id = ?;", (datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S"), ticket_id))
    finally:
        conn.close()


def ensure_demo_attendee_exists():
    demo_email = "attendee@example.com"
    attendee = db_get_attendee(demo_email)
    if not attendee:
        db_add_attendee(demo_email, "Attendee", 1, "Male Stag")
    elif not attendee.get("name"):
        db_add_attendee(
            demo_email,
            "Attendee",
            attendee.get("quantity", 1),
            attendee.get("category", "Male Stag"),
        )
