import asyncio

current_token: str | None = None
expires_at: float = 0.0
subscribers: list[asyncio.Queue] = []
session_subscribers: dict[str, list[asyncio.Queue]] = {}
current_base_url: str = ""
active_tokens: dict[str, float] = {}
session_tokens: dict[str, str] = {}
session_expires: dict[str, float] = {}
