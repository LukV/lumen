# lumen/server/sse.py

import json
from collections.abc import AsyncGenerator

from sse_starlette.sse import EventSourceResponse


def sse_error(code: str, message: str) -> EventSourceResponse:
    """Return an SSE response with a single error event."""

    async def stream() -> AsyncGenerator[dict[str, str]]:
        yield {
            "event": "error",
            "data": json.dumps({"code": code, "message": message}),
        }

    return EventSourceResponse(stream())