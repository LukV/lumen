"""Theme configuration for branded Lumen deployments."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from lumen.config import project_dir

logger = logging.getLogger("lumen.theme")


class ThemeColors(BaseModel):
    """Brand color configuration."""

    primary: str = "#4A2D4F"
    secondary: str = "#C2876E"
    accent: str = "#6B8F8A"
    palette: list[str] | None = None

    def resolved_palette(self) -> list[str]:
        """Return the full 6-color chart palette, deriving from primary/secondary/accent if not set."""
        if self.palette and len(self.palette) >= 3:
            return self.palette[:6] if len(self.palette) >= 6 else self.palette
        return [self.primary, self.secondary, self.accent, "#B8A44C", "#8C7B6B", "#A3667E"]


class ThemeFonts(BaseModel):
    """Typography configuration."""

    body: str = "DM Sans"
    editorial: str = "Source Serif 4"
    mono: str = "JetBrains Mono"
    custom_css: str | None = None


class ThemeConfig(BaseModel):
    """Visual identity configuration for a Lumen deployment."""

    app_name: str = "Lumen"
    logo_path: str | None = None
    locale: str = "en"
    colors: ThemeColors = ThemeColors()
    fonts: ThemeFonts = ThemeFonts()


def load_theme(connection_name: str | None = None) -> ThemeConfig:
    """Load theme configuration with fallback chain.

    Resolution order:
    1. ~/.lumen/projects/<connection>/theme.json (project-specific)
    2. ~/.lumen/theme.json (global)
    3. Built-in defaults
    """
    # Project-specific theme
    if connection_name:
        proj_path = project_dir(connection_name) / "theme.json"
        theme = _load_from(proj_path)
        if theme is not None:
            return theme

    # Global user theme
    global_path = Path.home() / ".lumen" / "theme.json"
    theme = _load_from(global_path)
    if theme is not None:
        return theme

    return ThemeConfig()


def _load_from(path: Path) -> ThemeConfig | None:
    """Load a ThemeConfig from a JSON file, returning None if missing or invalid."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return ThemeConfig.model_validate(data)
    except Exception:
        logger.warning("Failed to load theme from %s", path)
        return None


def theme_to_css_vars(theme: ThemeConfig) -> dict[str, str]:
    """Generate CSS custom property values from a theme."""
    palette = theme.colors.resolved_palette()
    return {
        "--accent": theme.colors.primary,
        "--accent-light": _lighten_hex(theme.colors.primary, 0.15),
        "--font-body": f'"{theme.fonts.body}", system-ui, sans-serif',
        "--font-editorial": f'"{theme.fonts.editorial}", Georgia, serif',
        "--font-mono": f'"{theme.fonts.mono}", monospace',
        "--logo-fill": theme.colors.primary,
        "--chart-palette": ",".join(palette),
    }


def theme_to_vegalite_config(theme: ThemeConfig) -> dict[str, Any]:
    """Generate a Vega-Lite theme config from a ThemeConfig."""
    palette = theme.colors.resolved_palette()
    font = f"{theme.fonts.body}, system-ui, sans-serif"

    return {
        "config": {
            "font": font,
            "axis": {
                "labelFont": font,
                "titleFont": font,
                "labelFontSize": 11,
                "titleFontSize": 12,
                "titleFontWeight": 600,
                "gridDash": [3, 3],
                "gridColor": "#E8E5DF",
                "domainColor": "#CCCAC5",
                "tickColor": "#CCCAC5",
                "labelLimit": 150,
                "titlePadding": 12,
            },
            "legend": {
                "labelFont": font,
                "titleFont": font,
                "labelFontSize": 11,
                "titleFontSize": 12,
            },
            "title": {
                "font": font,
                "fontSize": 14,
                "fontWeight": 600,
            },
            "bar": {"cornerRadiusEnd": 3},
            "line": {"strokeWidth": 2, "point": {"size": 40}},
            "point": {"size": 60, "opacity": 0.7},
            "area": {"opacity": 0.7, "line": True},
            "range": {"category": palette},
            "view": {"strokeWidth": 0},
            "padding": {"row": 10, "column": 10},
            "background": "transparent",
        },
    }


def _lighten_hex(hex_color: str, factor: float) -> str:
    """Lighten a hex color by a factor (0-1)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return f"#{hex_color}"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"
