import asyncio

current_token: str | None = None
expires_at: float = 0.0
subscribers: list[asyncio.Queue] = []
current_base_url: str = ""
active_tokens: dict[str, float] = {}
