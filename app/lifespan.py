import asyncio
from contextlib import asynccontextmanager

from app.config import BASE_URL, ROTATE_SECONDS
from app.db import ensure_demo_attendee_exists, init_db
from app.qr import rotate_token


async def rotation_loop():
    try:
        while True:
            await asyncio.sleep(ROTATE_SECONDS)
            rotate_token()
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app):
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
