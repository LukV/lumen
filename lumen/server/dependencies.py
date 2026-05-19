# lumen/server/dependencies.py

from typing import Annotated

from fastapi import Depends, Request

from lumen.server.state import AppState


def get_app_state(request: Request) -> AppState:
    """Dependency to retrieve the application state."""
    return request.app.state.app_state  # type: ignore[no-any-return]


StateDep = Annotated[AppState, Depends(get_app_state)]