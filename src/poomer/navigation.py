from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Self

from poomer.config import Config

VELOCITY_THRESHOLD: float = 15.0


@dataclass(slots=True)
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self: Self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self: Self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self: Self, scalar: float) -> Vec2:
        return Vec2(self.x * scalar, self.y * scalar)

    def __truediv__(self: Self, scalar: float) -> Vec2:
        return Vec2(self.x / scalar, self.y / scalar)

    @property
    def length(self: Self) -> float:
        return hypot(self.x, self.y)


@dataclass(slots=True)
class Mouse:
    curr: Vec2 = field(default_factory=Vec2)
    prev: Vec2 = field(default_factory=Vec2)
    drag: bool = False


@dataclass(slots=True)
class Camera:
    position: Vec2 = field(default_factory=Vec2)
    velocity: Vec2 = field(default_factory=Vec2)
    scale: float = 1.0
    delta_scale: float = 0.0
    scale_pivot: Vec2 = field(default_factory=Vec2)

    def world(self: Self, point: Vec2) -> Vec2:
        return point / self.scale

    def update(
        self: Self, config: Config, dt: float, mouse: Mouse, window_size: Vec2
    ) -> None:
        if abs(self.delta_scale) > 0.5:
            p0: Vec2 = (self.scale_pivot - window_size * 0.5) / self.scale
            self.scale = max(self.scale + self.delta_scale * dt, config.min_scale)
            p1: Vec2 = (self.scale_pivot - window_size * 0.5) / self.scale
            self.position = self.position + (p0 - p1)
            self.delta_scale -= self.delta_scale * dt * config.scale_friction

        if not mouse.drag and self.velocity.length > VELOCITY_THRESHOLD:
            self.position = self.position + self.velocity * dt
            self.velocity = self.velocity - self.velocity * dt * config.drag_friction


@dataclass(slots=True)
class Flashlight:
    enabled: bool = False
    shadow: float = 0.0
    radius: float = 200.0
    delta_radius: float = 0.0

    def update(self: Self, dt: float) -> None:
        if abs(self.delta_radius) > 1.0:
            self.radius = max(0.0, self.radius + self.delta_radius * dt)
            self.delta_radius -= self.delta_radius * 10.0 * dt

        if self.enabled:
            self.shadow = min(self.shadow + 6.0 * dt, 0.8)
        else:
            self.shadow = max(self.shadow - 6.0 * dt, 0.0)
