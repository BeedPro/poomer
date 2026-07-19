from __future__ import annotations

import argparse
import ctypes
import importlib
import sys
import time
from importlib import resources
from pathlib import Path
from typing import NamedTuple

import mss
import pyglet
from pyglet.display import Screen

from poomer import __version__
from poomer.config import (
    Config,
    default_config_path,
    generate_default_config,
    load_config,
)
from poomer.navigation import Camera, Flashlight, Mouse, Vec2

pyglet.options["shadow_window"] = False
gl = importlib.import_module("pyglet.gl")
pyglet_window = importlib.import_module("pyglet.window")
key = importlib.import_module("pyglet.window.key")
mouse = importlib.import_module("pyglet.window.mouse")
pyglet_xlib_window = importlib.import_module("pyglet.window.xlib")
NoSuchConfigException = pyglet_window.NoSuchConfigException
XlibWindow = pyglet_xlib_window.XlibWindow


INITIAL_FL_DELTA_RADIUS: float = 250.0


class PointerPosition(NamedTuple):
    x: int
    y: int


class Xlib:
    def __init__(self) -> None:
        self.lib: ctypes.CDLL = ctypes.CDLL("libX11.so.6")
        self.display: ctypes.c_void_p | None = None
        self.root: int = 0
        self.lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.lib.XOpenDisplay.restype = ctypes.c_void_p
        self.lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.lib.XDefaultRootWindow.restype = ctypes.c_ulong
        self.lib.XQueryPointer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint),
        ]
        self.lib.XQueryPointer.restype = ctypes.c_int
        self.lib.XCloseDisplay.argtypes = [ctypes.c_void_p]

    def __enter__(self) -> Xlib:
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("Could not open X display")
        self.root = self.lib.XDefaultRootWindow(self.display)
        return self

    def __exit__(self, *_args: object) -> None:
        self.lib.XCloseDisplay(self.display)

    def pointer_position(self) -> PointerPosition:
        root_return: ctypes.c_ulong = ctypes.c_ulong()
        child_return: ctypes.c_ulong = ctypes.c_ulong()
        root_x: ctypes.c_int = ctypes.c_int()
        root_y: ctypes.c_int = ctypes.c_int()
        win_x: ctypes.c_int = ctypes.c_int()
        win_y: ctypes.c_int = ctypes.c_int()
        mask: ctypes.c_uint = ctypes.c_uint()
        if not self.lib.XQueryPointer(
            self.display,
            self.root,
            ctypes.byref(root_return),
            ctypes.byref(child_return),
            ctypes.byref(root_x),
            ctypes.byref(root_y),
            ctypes.byref(win_x),
            ctypes.byref(win_y),
            ctypes.byref(mask),
        ):
            raise RuntimeError("Could not query pointer position")
        return PointerPosition(root_x.value, root_y.value)


def _query_pointer_position() -> PointerPosition:
    with Xlib() as xlib:
        return xlib.pointer_position()


def pointer_position() -> PointerPosition | None:
    try:
        return _query_pointer_position()
    except (OSError, RuntimeError):
        return None


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


WINDOW_CONFIGS: tuple[gl.Config, ...] = (
    gl.Config(double_buffer=True, depth_size=24),
    gl.Config(double_buffer=True, depth_size=16),
    gl.Config(double_buffer=True),
    gl.Config(),
)


class Screenshot:
    def __init__(self) -> None:
        self.width: int
        self.height: int
        self.data: bytes
        self.width, self.height, self.data = self._capture()

    @staticmethod
    def _capture() -> tuple[int, int, bytes]:
        with mss.mss() as screen_capture:
            monitor = screen_capture.monitors[1]
            image = screen_capture.grab(monitor)
        return image.width, image.height, bytes(image.bgra)


def read_shader(name: str) -> str:
    return resources.files("poomer.shaders").joinpath(name).read_text()


def shader_info_log(shader: int) -> str:
    length: gl.GLint = gl.GLint()
    gl.glGetShaderiv(shader, gl.GL_INFO_LOG_LENGTH, ctypes.byref(length))
    if length.value <= 1:
        return ""
    buffer = ctypes.create_string_buffer(length.value)
    gl.glGetShaderInfoLog(shader, length, None, buffer)
    return buffer.value.decode(errors="replace")


def program_info_log(program: int) -> str:
    length: gl.GLint = gl.GLint()
    gl.glGetProgramiv(program, gl.GL_INFO_LOG_LENGTH, ctypes.byref(length))
    if length.value <= 1:
        return ""
    buffer = ctypes.create_string_buffer(length.value)
    gl.glGetProgramInfoLog(program, length, None, buffer)
    return buffer.value.decode(errors="replace")


def compile_shader(source: str, shader_type: int) -> int:
    shader: int = gl.glCreateShader(shader_type)
    source_buffer = ctypes.create_string_buffer(source.encode())
    source_pointer = ctypes.cast(
        ctypes.pointer(ctypes.pointer(source_buffer)),
        ctypes.POINTER(ctypes.POINTER(gl.GLchar)),
    )
    length: gl.GLint = gl.GLint(len(source_buffer.value))
    gl.glShaderSource(shader, 1, source_pointer, ctypes.byref(length))
    gl.glCompileShader(shader)

    success: gl.GLint = gl.GLint()
    gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS, ctypes.byref(success))
    if not success.value:
        raise RuntimeError(shader_info_log(shader))
    return shader


def create_shader_program() -> int:
    vertex: int = compile_shader(read_shader("vert.glsl"), gl.GL_VERTEX_SHADER)
    fragment: int = compile_shader(read_shader("frag.glsl"), gl.GL_FRAGMENT_SHADER)
    program: int = gl.glCreateProgram()
    gl.glAttachShader(program, vertex)
    gl.glAttachShader(program, fragment)
    gl.glBindAttribLocation(program, 0, b"aPos")
    gl.glBindAttribLocation(program, 1, b"aTexCoord")
    gl.glLinkProgram(program)
    gl.glDeleteShader(vertex)
    gl.glDeleteShader(fragment)

    success: gl.GLint = gl.GLint()
    gl.glGetProgramiv(program, gl.GL_LINK_STATUS, ctypes.byref(success))
    if not success.value:
        raise RuntimeError(program_info_log(program))
    return program


def uniform_location(program: int, name: str) -> int:
    return gl.glGetUniformLocation(program, name.encode())


class PoomerWindow(XlibWindow):
    def __init__(
        self,
        config: Config,
        config_path: Path,
        windowed: bool,
        pointer_restore: PointerPosition | None,
    ) -> None:
        self.screenshot: Screenshot = Screenshot()
        display = pyglet.display.get_display()
        screen = display.get_default_screen()
        width: int = min(self.screenshot.width, screen.width)
        height: int = min(self.screenshot.height, screen.height)
        self._create_window(screen, width, height, windowed)
        self.app_config: Config = config
        self.config_path: Path = config_path
        self.camera: Camera = Camera(scale=1.0)
        cursor: Vec2 = self.window_pointer_position(pointer_restore)
        self.mouse_state: Mouse = Mouse(curr=cursor, prev=cursor)
        self.flashlight: Flashlight = Flashlight()
        self.mirror: bool = False
        self.ctrl_down: bool = False
        self.rate: float = float(screen.get_mode().rate or 60)
        self.set_mouse_visible(True)

        self.shader: int = create_shader_program()
        self.vao: gl.GLuint = gl.GLuint()
        self.vbo: gl.GLuint = gl.GLuint()
        self.ebo: gl.GLuint = gl.GLuint()
        self.texture: gl.GLuint = gl.GLuint()
        self.create_buffers()
        self.create_texture()
        pyglet.clock.schedule_interval(self.update, 1.0 / self.rate)

    def _try_window_config(
        self, screen: Screen, width: int, height: int, windowed: bool, window_config: object
    ) -> bool:
        try:
            style = (
                None if windowed else pyglet.window.Window.WINDOW_STYLE_BORDERLESS
            )
            super().__init__(
                width=width,
                height=height,
                caption="poomer",
                fullscreen=False,
                resizable=windowed,
                style=style,
                screen=screen,
                vsync=True,
                config=window_config,
            )
            self.set_location(screen.x, screen.y)
            return True
        except NoSuchConfigException:
            return False

    def _create_window(
        self, screen: Screen, width: int, height: int, windowed: bool
    ) -> None:
        for window_config in WINDOW_CONFIGS:
            if self._try_window_config(screen, width, height, windowed, window_config):
                return
        raise RuntimeError(
            "Could not create an OpenGL window. Make sure this is running under "
            "X11/GLX with a working OpenGL driver. If you are using Nix as a "
            "package manager on a non-NixOS distro, run `poomer-nixgl-nvidia` "
            "for NVIDIA or `poomer-nixgl-mesa` for Mesa/AMD/Intel."
        )

    def window_pointer_position(self, position: PointerPosition | None) -> Vec2:
        if position is None:
            return Vec2()
        window_x: int
        window_y: int
        window_x, window_y = self.get_location()
        x: float = clamp(float(position.x - window_x), 0.0, float(self.width))
        y: float = clamp(float(position.y - window_y), 0.0, float(self.height))
        return Vec2(
            x,
            float(self.height) - y,
        )

    def create_buffers(self) -> None:
        w: float = float(self.screenshot.width)
        h: float = float(self.screenshot.height)
        vertices = (gl.GLfloat * 16)(
            w,
            0.0,
            1.0,
            1.0,
            w,
            h,
            1.0,
            0.0,
            0.0,
            h,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        )
        indices = (gl.GLuint * 6)(0, 1, 3, 1, 2, 3)

        gl.glGenVertexArrays(1, ctypes.byref(self.vao))
        gl.glGenBuffers(1, ctypes.byref(self.vbo))
        gl.glGenBuffers(1, ctypes.byref(self.ebo))
        gl.glBindVertexArray(self.vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER,
            gl.GLsizeiptr(ctypes.sizeof(vertices)),
            vertices,
            gl.GL_STATIC_DRAW,
        )
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(
            gl.GL_ELEMENT_ARRAY_BUFFER,
            gl.GLsizeiptr(ctypes.sizeof(indices)),
            indices,
            gl.GL_STATIC_DRAW,
        )

        stride: int = 4 * ctypes.sizeof(gl.GLfloat)
        gl.glVertexAttribPointer(
            0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0)
        )
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(
            1,
            2,
            gl.GL_FLOAT,
            gl.GL_FALSE,
            stride,
            ctypes.c_void_p(2 * ctypes.sizeof(gl.GLfloat)),
        )
        gl.glEnableVertexAttribArray(1)

    def create_texture(self) -> None:
        gl.glGenTextures(1, ctypes.byref(self.texture))
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        data: ctypes.Array[ctypes.c_char] = ctypes.create_string_buffer(self.screenshot.data)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGB,
            self.screenshot.width,
            self.screenshot.height,
            0,
            gl.GL_BGRA,
            gl.GL_UNSIGNED_BYTE,
            data,
        )
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(
            gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER
        )
        gl.glTexParameteri(
            gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER
        )

    def _scroll_zoom(self, direction: float) -> None:
        self.camera.delta_scale += self.app_config.scroll_speed * direction
        self.camera.scale_pivot = self.mouse_state.curr

    def _scroll_flashlight(self, direction: float) -> None:
        d: float = -1.0 if self.app_config.reverse_highlight_scroll else 1.0
        self.flashlight.delta_radius += INITIAL_FL_DELTA_RADIUS * d * direction

    def scroll_up(self) -> None:
        if self.ctrl_down and self.flashlight.enabled:
            self._scroll_flashlight(1.0)
        else:
            self._scroll_zoom(1.0)

    def scroll_down(self) -> None:
        if self.ctrl_down and self.flashlight.enabled:
            self._scroll_flashlight(-1.0)
        else:
            self._scroll_zoom(-1.0)

    def on_draw(self) -> None:
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glUseProgram(self.shader)
        gl.glUniform2f(
            uniform_location(self.shader, "cameraPos"),
            self.camera.position.x,
            self.camera.position.y,
        )
        gl.glUniform1f(uniform_location(self.shader, "cameraScale"), self.camera.scale)
        gl.glUniform2f(
            uniform_location(self.shader, "screenshotSize"),
            self.screenshot.width,
            self.screenshot.height,
        )
        gl.glUniform2f(
            uniform_location(self.shader, "windowSize"), self.width, self.height
        )
        gl.glUniform2f(
            uniform_location(self.shader, "cursorPos"),
            self.mouse_state.curr.x,
            self.mouse_state.curr.y,
        )
        gl.glUniform1f(
            uniform_location(self.shader, "flShadow"), self.flashlight.shadow
        )
        gl.glUniform1f(
            uniform_location(self.shader, "flRadius"), self.flashlight.radius
        )
        gl.glUniform1i(uniform_location(self.shader, "mirror"), 1 if self.mirror else 0)
        gl.glUniform1i(uniform_location(self.shader, "tex"), 0)
        gl.glBindVertexArray(self.vao)
        gl.glDrawElements(gl.GL_TRIANGLES, 6, gl.GL_UNSIGNED_INT, None)

    def update(self, dt: float) -> None:
        self.camera.update(
            self.app_config,
            dt,
            self.mouse_state,
            Vec2(float(self.width), float(self.height)),
        )
        self.flashlight.update(dt)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        del dx, dy
        self.mouse_state.curr = Vec2(float(x), float(self.height - y))
        self.mouse_state.prev = self.mouse_state.curr

    def _handle_drag(self) -> None:
        delta: Vec2 = self.camera.world(self.mouse_state.prev) - self.camera.world(
            self.mouse_state.curr
        )
        self.camera.position = self.camera.position + delta
        self.camera.velocity = delta * self.rate

    def on_mouse_drag(
        self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int
    ) -> None:
        del dx, dy, modifiers
        self.mouse_state.curr = Vec2(float(x), float(self.height - y))
        if buttons & mouse.LEFT:
            self._handle_drag()
        self.mouse_state.prev = self.mouse_state.curr

    def _handle_press(self) -> None:
        self.mouse_state.prev = self.mouse_state.curr
        self.mouse_state.drag = True
        self.camera.velocity = Vec2()

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        del modifiers
        self.mouse_state.curr = Vec2(float(x), float(self.height - y))
        if button == mouse.LEFT:
            self._handle_press()

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        del x, y, modifiers
        if button == mouse.LEFT:
            self.mouse_state.drag = False

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float, scroll_y: float) -> None:
        del scroll_x
        self.mouse_state.curr = Vec2(float(x), float(self.height - y))
        if scroll_y > 0:
            self.scroll_up()
        elif scroll_y < 0:
            self.scroll_down()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        del modifiers
        if symbol in (key.LCTRL, key.RCTRL):
            self.ctrl_down = True
        elif symbol in (key.EQUAL, key.NUM_ADD):
            self.scroll_up()
        elif symbol in (key.MINUS, key.NUM_SUBTRACT):
            self.scroll_down()
        elif symbol == key._0:
            self.camera = Camera(scale=1.0)
            self.mirror = False
        elif symbol in (key.Q, key.ESCAPE):
            self.close()
        elif symbol == key.R and self.config_path.exists():
            self.app_config = load_config(self.config_path)
            print(f"Reloaded config: {self.app_config}")
        elif symbol == key.M:
            self.camera.position.x += self.screenshot.width / self.camera.scale - 2 * (
                self.mouse_state.curr.x / self.camera.scale + self.camera.position.x
            )
            self.mirror = not self.mirror
        elif symbol == key.F:
            self.flashlight.enabled = not self.flashlight.enabled

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        del modifiers
        if symbol in (key.LCTRL, key.RCTRL):
            self.ctrl_down = False

    def close(self) -> None:
        pyglet.clock.unschedule(self.update)
        gl.glDeleteTextures(1, ctypes.byref(self.texture))
        gl.glDeleteBuffers(1, ctypes.byref(self.vbo))
        gl.glDeleteBuffers(1, ctypes.byref(self.ebo))
        gl.glDeleteVertexArrays(1, ctypes.byref(self.vao))
        gl.glDeleteProgram(self.shader)
        super().close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="poomer")
    parser.add_argument(
        "-d", "--delay", type=float, default=0.0, help="delay execution by seconds"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=default_config_path(),
        help="config file path",
    )
    parser.add_argument(
        "--new-config",
        nargs="?",
        const=default_config_path(),
        type=Path,
        help="generate a default config",
    )
    parser.add_argument(
        "-w",
        "--windowed",
        action="store_true",
        help="windowed mode instead of fullscreen",
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"poomer-{__version__}"
    )
    return parser.parse_args(argv)


def _handle_new_config(config_path: Path) -> int:
    if config_path.exists() and input(f"File {config_path} already exists. Replace it? [yn] ").lower() != "y":
        print("Disaster prevented")
        return 1
    generate_default_config(config_path)
    print(f"Generated config at {config_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(sys.argv[1:] if argv is None else argv)
    if args.new_config is not None:
        return _handle_new_config(args.new_config)

    if args.delay > 0:
        time.sleep(args.delay)

    config: Config = Config()
    if args.config.exists():
        config = load_config(args.config)
    else:
        print(f"{args.config} doesn't exist. Using default values.", file=sys.stderr)
    print(f"Using config: {config}")

    original_pointer_position: PointerPosition | None = pointer_position()
    PoomerWindow(config, args.config, args.windowed, original_pointer_position)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
