import asyncio

from starlette.types import Receive, Scope, Send


class GracefulShutdownMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        try:
            await self.app(scope, receive, send)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
