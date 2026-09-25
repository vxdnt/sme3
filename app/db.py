import sqlite3

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
                            ticket_sent BOOLEAN NOT NULL DEFAULT FALSE,
                            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                    """)
                    cur.execute(
                        "ALTER TABLE attendees ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'Male Stag';"
                    )
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
            cur = conn.execute(
                "SELECT email, name, quantity, category, ticket_sent, created_at FROM attendees WHERE email = ?",
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
            a.ticket_sent,
            a.created_at,
            COUNT(c.id) AS times_scanned,
            MIN(c.scanned_at) AS first_scan,
            MAX(c.scanned_at) AS last_scan
        FROM attendees a
        LEFT JOIN check_ins c ON LOWER(c.email) = LOWER(a.email)
        GROUP BY a.email, a.name, a.quantity, a.category, a.ticket_sent, a.created_at
        ORDER BY a.created_at ASC;
    """
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    result = []
                    for r in cur.fetchall():
                        d = dict(r)
                        for key in ("first_scan", "last_scan", "created_at"):
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


def db_get_attendee(email: str):
    email = email.lower().strip()
    query = """
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
        WHERE LOWER(a.email) = {placeholder}
        GROUP BY a.email, a.name, a.quantity, a.category, a.ticket_sent, a.created_at;
    """
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(query.format(placeholder="%s"), (email,))
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

    conn = get_sqlite_connection()
    try:
        with conn:
            row = conn.execute(query.format(placeholder="?"), (email,)).fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def db_record_checkin(email: str, scan_id: str, device_id: str, ip: str, device_type: str, os_name: str, browser: str, scanned_at: str):
    email = email.lower().strip()
    attendee = db_get_attendee(email) or {}
    attendee_name = (attendee.get("name") or email.split("@")[0].capitalize() or "").strip()
    if IS_POSTGRES:
        conn = get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM attendees WHERE LOWER(email) = %s;", (email,))
                    row = cur.fetchone()
                    if row and row.get("name"):
                        attendee_name = row["name"]

                    cur.execute(
                        "SELECT COUNT(*) AS cnt, MAX(scanned_at) AS last FROM check_ins WHERE LOWER(email) = %s;",
                        (email,),
                    )
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

    conn = get_sqlite_connection()
    try:
        with conn:
            row = conn.execute("SELECT name FROM attendees WHERE LOWER(email) = ?;", (email,)).fetchone()
            if row and row["name"]:
                attendee_name = row["name"]

            stat = conn.execute(
                "SELECT COUNT(*) AS cnt, MAX(scanned_at) AS last FROM check_ins WHERE LOWER(email) = ?;",
                (email,),
            ).fetchone()
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
        return

    conn = get_sqlite_connection()
    try:
        with conn:
            conn.execute("UPDATE attendees SET ticket_sent = 1 WHERE LOWER(email) = ?;", (email,))
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
