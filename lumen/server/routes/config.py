# lumen/server/routes/config.py

from typing import Any

from fastapi import APIRouter

from lumen.server.dependencies import StateDep
from lumen.theme import load_theme, theme_to_css_vars

router = APIRouter()


@router.get("/theme")
async def get_theme(state: StateDep) -> dict[str, Any]:
    theme = load_theme(state.config.active_connection)

    return {
        "app_name": theme.app_name,
        "locale": theme.locale,
        "logo_path": theme.logo_path,
        "custom_css": theme.fonts.custom_css,
        "css_vars": theme_to_css_vars(theme),
    }


@router.get("/config")
async def get_config(state: StateDep) -> dict[str, Any]:
    return {
        "active_connection": state.config.active_connection,
        "has_connection": state.config.active_connection is not None,
        "connections": list(state.config.connections.keys()),
    }