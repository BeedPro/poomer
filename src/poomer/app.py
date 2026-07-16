from __future__ import annotations

import argparse
import ctypes
import sys
import time
from importlib import resources
from pathlib import Path

import mss
import pyglet

pyglet.options["shadow_window"] = False

from pyglet import gl
from pyglet.window import key, mouse

from poomer import __version__
from poomer.config import Config, default_config_path, generate_default_config, load_config
from poomer.navigation import Camera, Flashlight, Mouse, Vec2


INITIAL_FL_DELTA_RADIUS = 250.0


class Screenshot:
    def __init__(self) -> None:
        with mss.mss() as screen_capture:
            monitor = screen_capture.monitors[1]
            image = screen_capture.grab(monitor)

        self.width = image.width
        self.height = image.height
        self.data = bytes(image.bgra)


def read_shader(name: str) -> str:
    return resources.files("poomer.shaders").joinpath(name).read_text()


def shader_info_log(shader: gl.GLuint) -> str:
    length = gl.GLint()
    gl.glGetShaderiv(shader, gl.GL_INFO_LOG_LENGTH, ctypes.byref(length))
    if length.value <= 1:
        return ""
    buffer = ctypes.create_string_buffer(length.value)
    gl.glGetShaderInfoLog(shader, length, None, buffer)
    return buffer.value.decode(errors="replace")


def program_info_log(program: gl.GLuint) -> str:
    length = gl.GLint()
    gl.glGetProgramiv(program, gl.GL_INFO_LOG_LENGTH, ctypes.byref(length))
    if length.value <= 1:
        return ""
    buffer = ctypes.create_string_buffer(length.value)
    gl.glGetProgramInfoLog(program, length, None, buffer)
    return buffer.value.decode(errors="replace")


def compile_shader(source: str, shader_type: int) -> gl.GLuint:
    shader = gl.glCreateShader(shader_type)
    source_buffer = ctypes.create_string_buffer(source.encode())
    source_pointer = ctypes.cast(ctypes.pointer(ctypes.pointer(source_buffer)), ctypes.POINTER(ctypes.POINTER(gl.GLchar)))
    length = gl.GLint(len(source_buffer.value))
    gl.glShaderSource(shader, 1, source_pointer, ctypes.byref(length))
    gl.glCompileShader(shader)

    success = gl.GLint()
    gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS, ctypes.byref(success))
    if not success.value:
        raise RuntimeError(shader_info_log(shader))
    return shader


def create_shader_program() -> gl.GLuint:
    vertex = compile_shader(read_shader("vert.glsl"), gl.GL_VERTEX_SHADER)
    fragment = compile_shader(read_shader("frag.glsl"), gl.GL_FRAGMENT_SHADER)
    program = gl.glCreateProgram()
    gl.glAttachShader(program, vertex)
    gl.glAttachShader(program, fragment)
    gl.glBindAttribLocation(program, 0, b"aPos")
    gl.glBindAttribLocation(program, 1, b"aTexCoord")
    gl.glLinkProgram(program)
    gl.glDeleteShader(vertex)
    gl.glDeleteShader(fragment)

    success = gl.GLint()
    gl.glGetProgramiv(program, gl.GL_LINK_STATUS, ctypes.byref(success))
    if not success.value:
        raise RuntimeError(program_info_log(program))
    return program


def uniform_location(program: gl.GLuint, name: str) -> int:
    return gl.glGetUniformLocation(program, name.encode())


class PoomerWindow(pyglet.window.Window):
    def __init__(self, config: Config, config_path: Path, windowed: bool) -> None:
        self.screenshot = Screenshot()
        display = pyglet.display.get_display()
        screen = display.get_default_screen()
        width = min(self.screenshot.width, screen.width)
        height = min(self.screenshot.height, screen.height)
        super().__init__(
            width=width,
            height=height,
            caption="boomer",
            fullscreen=not windowed,
            resizable=windowed,
            vsync=True,
        )

        self.config = config
        self.config_path = config_path
        self.camera = Camera(scale=1.0)
        self.mouse_state = Mouse()
        self.flashlight = Flashlight()
        self.mirror = False
        self.ctrl_down = False
        self.rate = float(screen.get_mode().rate or 60)

        self.shader = create_shader_program()
        self.vao = gl.GLuint()
        self.vbo = gl.GLuint()
        self.ebo = gl.GLuint()
        self.texture = gl.GLuint()
        self.create_buffers()
        self.create_texture()
        pyglet.clock.schedule_interval(self.update, 1.0 / self.rate)

    def create_buffers(self) -> None:
        w = float(self.screenshot.width)
        h = float(self.screenshot.height)
        vertices = (gl.GLfloat * 16)(
            w, 0.0, 1.0, 1.0,
            w, h, 1.0, 0.0,
            0.0, h, 0.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        )
        indices = (gl.GLuint * 6)(0, 1, 3, 1, 2, 3)

        gl.glGenVertexArrays(1, ctypes.byref(self.vao))
        gl.glGenBuffers(1, ctypes.byref(self.vbo))
        gl.glGenBuffers(1, ctypes.byref(self.ebo))
        gl.glBindVertexArray(self.vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(vertices), vertices, gl.GL_STATIC_DRAW)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, ctypes.sizeof(indices), indices, gl.GL_STATIC_DRAW)

        stride = 4 * ctypes.sizeof(gl.GLfloat)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(2 * ctypes.sizeof(gl.GLfloat)))
        gl.glEnableVertexAttribArray(1)

    def create_texture(self) -> None:
        gl.glGenTextures(1, ctypes.byref(self.texture))
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        data = ctypes.create_string_buffer(self.screenshot.data)
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
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)

    def scroll_up(self) -> None:
        if self.ctrl_down and self.flashlight.enabled:
            self.flashlight.delta_radius += INITIAL_FL_DELTA_RADIUS
        else:
            self.camera.delta_scale += self.config.scroll_speed
            self.camera.scale_pivot = self.mouse_state.curr

    def scroll_down(self) -> None:
        if self.ctrl_down and self.flashlight.enabled:
            self.flashlight.delta_radius -= INITIAL_FL_DELTA_RADIUS
        else:
            self.camera.delta_scale -= self.config.scroll_speed
            self.camera.scale_pivot = self.mouse_state.curr

    def on_draw(self) -> None:
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glUseProgram(self.shader)
        gl.glUniform2f(uniform_location(self.shader, "cameraPos"), self.camera.position.x, self.camera.position.y)
        gl.glUniform1f(uniform_location(self.shader, "cameraScale"), self.camera.scale)
        gl.glUniform2f(uniform_location(self.shader, "screenshotSize"), self.screenshot.width, self.screenshot.height)
        gl.glUniform2f(uniform_location(self.shader, "windowSize"), self.width, self.height)
        gl.glUniform2f(uniform_location(self.shader, "cursorPos"), self.mouse_state.curr.x, self.mouse_state.curr.y)
        gl.glUniform1f(uniform_location(self.shader, "flShadow"), self.flashlight.shadow)
        gl.glUniform1f(uniform_location(self.shader, "flRadius"), self.flashlight.radius)
        gl.glUniform1i(uniform_location(self.shader, "mirror"), 1 if self.mirror else 0)
        gl.glUniform1i(uniform_location(self.shader, "tex"), 0)
        gl.glBindVertexArray(self.vao)
        gl.glDrawElements(gl.GL_TRIANGLES, 6, gl.GL_UNSIGNED_INT, None)

    def update(self, dt: float) -> None:
        self.camera.update(self.config, dt, self.mouse_state, Vec2(float(self.width), float(self.height)))
        self.flashlight.update(dt)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        self.mouse_state.curr = Vec2(float(x), float(self.height - y))
        self.mouse_state.prev = self.mouse_state.curr

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> None:
        self.mouse_state.curr = Vec2(float(x), float(self.height - y))
        if buttons & mouse.LEFT:
            delta = self.camera.world(self.mouse_state.prev) - self.camera.world(self.mouse_state.curr)
            self.camera.position = self.camera.position + delta
            self.camera.velocity = delta * self.rate
        self.mouse_state.prev = self.mouse_state.curr

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self.mouse_state.curr = Vec2(float(x), float(self.height - y))
        if button == mouse.LEFT:
            self.mouse_state.prev = self.mouse_state.curr
            self.mouse_state.drag = True
            self.camera.velocity = Vec2()

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if button == mouse.LEFT:
            self.mouse_state.drag = False

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float, scroll_y: float) -> None:
        self.mouse_state.curr = Vec2(float(x), float(self.height - y))
        if scroll_y > 0:
            self.scroll_up()
        elif scroll_y < 0:
            self.scroll_down()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
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
        elif symbol == key.R:
            if self.config_path.exists():
                self.config = load_config(self.config_path)
                print(f"Reloaded config: {self.config}")
        elif symbol == key.M:
            self.camera.position.x += self.screenshot.width / self.camera.scale - 2 * (
                self.mouse_state.curr.x / self.camera.scale + self.camera.position.x
            )
            self.mirror = not self.mirror
        elif symbol == key.F:
            self.flashlight.enabled = not self.flashlight.enabled

    def on_key_release(self, symbol: int, modifiers: int) -> None:
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
    parser.add_argument("-d", "--delay", type=float, default=0.0, help="delay execution by seconds")
    parser.add_argument("-c", "--config", type=Path, default=default_config_path(), help="config file path")
    parser.add_argument("--new-config", nargs="?", const=default_config_path(), type=Path, help="generate a default config")
    parser.add_argument("-w", "--windowed", action="store_true", help="windowed mode instead of fullscreen")
    parser.add_argument("-V", "--version", action="version", version=f"poomer-{__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.new_config is not None:
        if args.new_config.exists():
            answer = input(f"File {args.new_config} already exists. Replace it? [yn] ")
            if answer.lower() != "y":
                print("Disaster prevented")
                return 1
        generate_default_config(args.new_config)
        print(f"Generated config at {args.new_config}")
        return 0

    if args.delay > 0:
        time.sleep(args.delay)

    config = Config()
    if args.config.exists():
        config = load_config(args.config)
    else:
        print(f"{args.config} doesn't exist. Using default values.", file=sys.stderr)
    print(f"Using config: {config}")

    PoomerWindow(config, args.config, args.windowed)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
