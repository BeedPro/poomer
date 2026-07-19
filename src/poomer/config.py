from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Config:
    min_scale: float = 0.4
    scroll_speed: float = 1.6
    drag_friction: float = 8.0
    scale_friction: float = 4.0
    reverse_highlight_scroll: bool = True


DEFAULT_CONFIG: Config = Config()


def parse_bool(value: str) -> bool:
    if value.lower() in ("true", "yes", "on", "1"):
        return True
    if value.lower() in ("false", "no", "off", "0"):
        return False
    raise ValueError(f"expected boolean value, got {value!r}")


def default_config_path() -> Path:
    return Path.home() / ".config" / "poomer" / "config"


def _set_config_value(config: Config, key: str, value: str) -> None:
    if key == "min_scale":
        config.min_scale = float(value)
    elif key == "scroll_speed":
        config.scroll_speed = float(value)
    elif key == "drag_friction":
        config.drag_friction = float(value)
    elif key == "scale_friction":
        config.scale_friction = float(value)
    elif key == "reverse_highlight_scroll":
        config.reverse_highlight_scroll = parse_bool(value)
    else:
        raise ValueError(f"unknown config key {key!r}")


def load_config(path: Path) -> Config:
    config: Config = Config(
        min_scale=DEFAULT_CONFIG.min_scale,
        scroll_speed=DEFAULT_CONFIG.scroll_speed,
        drag_friction=DEFAULT_CONFIG.drag_friction,
        scale_friction=DEFAULT_CONFIG.scale_friction,
        reverse_highlight_scroll=DEFAULT_CONFIG.reverse_highlight_scroll,
    )

    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line: str = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected key = value")

        key: str
        value: str
        key, value = (part.strip() for part in line.split("=", 1))
        _set_config_value(config, key, value)

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
