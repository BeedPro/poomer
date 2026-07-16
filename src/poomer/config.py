from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Config:
    min_scale: float = 0.01
    scroll_speed: float = 1.5
    drag_friction: float = 6.0
    scale_friction: float = 4.0
    reverse_highlight_scroll: bool = True


DEFAULT_CONFIG = Config()


def parse_bool(value: str) -> bool:
    match value.lower():
        case "true" | "yes" | "on" | "1":
            return True
        case "false" | "no" | "off" | "0":
            return False
        case _:
            raise ValueError(f"expected boolean value, got {value!r}")


def default_config_path() -> Path:
    return Path.home() / ".config" / "poomer" / "config"


def load_config(path: Path) -> Config:
    config = Config(
        min_scale=DEFAULT_CONFIG.min_scale,
        scroll_speed=DEFAULT_CONFIG.scroll_speed,
        drag_friction=DEFAULT_CONFIG.drag_friction,
        scale_friction=DEFAULT_CONFIG.scale_friction,
        reverse_highlight_scroll=DEFAULT_CONFIG.reverse_highlight_scroll,
    )

    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected key = value")

        key, value = (part.strip() for part in line.split("=", 1))
        match key:
            case "min_scale":
                config.min_scale = float(value)
            case "scroll_speed":
                config.scroll_speed = float(value)
            case "drag_friction":
                config.drag_friction = float(value)
            case "scale_friction":
                config.scale_friction = float(value)
            case "reverse_highlight_scroll":
                try:
                    config.reverse_highlight_scroll = parse_bool(value)
                except ValueError as error:
                    raise ValueError(f"{path}:{line_number}: {error}") from error
            case _:
                raise ValueError(f"{path}:{line_number}: unknown config key {key!r}")

    return config


def generate_default_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                f"min_scale = {DEFAULT_CONFIG.min_scale}",
                f"scroll_speed = {DEFAULT_CONFIG.scroll_speed}",
                f"drag_friction = {DEFAULT_CONFIG.drag_friction}",
                f"scale_friction = {DEFAULT_CONFIG.scale_friction}",
                f"reverse_highlight_scroll = {str(DEFAULT_CONFIG.reverse_highlight_scroll).lower()}",
                "",
            )
        )
    )
