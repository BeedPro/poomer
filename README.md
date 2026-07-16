# Poomer

Python screen zoomer inspired by the original Nim implementation.

## Quick Start

```console
$ uv pip install -e .
$ poomer --help
$ poomer
```

Build distributions with `uv`:

```console
$ uv build
```

With Nix flakes:

```console
$ nix develop
$ poomer --help
$ poomer
```

On non-NixOS distributions, run the OpenGL window through `nixGL`:

```console
$ nix develop
$ poomer-nixgl
```

If the default wrapper does not match your graphics driver, use one of the explicit wrappers:

```console
$ poomer-nixgl-mesa    # AMD/Intel Mesa drivers
$ poomer-nixgl-nvidia  # NVIDIA proprietary drivers
```

The `poomer-nixgl*` commands are provided by this flake and fetch the locked `nixGL` wrapper through Nix. You do not need distro packages for these when using Nix; install the system dependencies below only when running Poomer outside Nix.

## System Dependencies

Poomer uses `pyglet` for the OpenGL window and `mss` for screen capture. Install Python, uv, and OpenGL/X11 runtime libraries for your distro.

Debian/Ubuntu:

```console
$ sudo apt-get install python3 uv libgl1-mesa-dev libglu1-mesa libx11-6 libxcursor1 libxext6 libxi6 libxinerama1 libxrandr2
```

Void Linux:

```console
$ sudo xbps-install -S python3 uv libglvnd glu libX11 libXcursor libXext libXi libXinerama libXrandr
```

Arch Linux:

```console
$ sudo pacman -S python uv libglvnd glu libx11 libxcursor libxext libxi libxinerama libxrandr
```

Fedora:

```console
$ sudo dnf install python3 uv mesa-libGL mesa-libGLU libX11 libXcursor libXext libXi libXinerama libXrandr
```

## Controls

| Control | Description |
| --- | --- |
| <kbd>0</kbd> | Reset position, scale, velocity, and mirroring. |
| <kbd>q</kbd> or <kbd>ESC</kbd> | Quit. |
| <kbd>r</kbd> | Reload configuration. |
| <kbd>m</kbd> | Mirror the image. |
| <kbd>f</kbd> | Toggle flashlight effect. |
| Drag with left mouse button | Move the image around. |
| Scroll wheel or <kbd>=</kbd>/<kbd>-</kbd> | Zoom in/out. |
| <kbd>Ctrl</kbd> + Scroll wheel | Change the flashlight radius. |

## Configuration

The default config file is `$HOME/.config/poomer/config`.

```console
$ poomer --new-config
```

Supported parameters:

| Name | Description |
| --- | --- |
| `min_scale` | The smallest scale allowed when zooming out. |
| `scroll_speed` | How quickly scrolling zooms in/out. |
| `drag_friction` | How quickly movement slows after dragging. |
| `scale_friction` | How quickly zoom momentum slows after scrolling. |
| `reverse_highlight_scroll` | Reverse Ctrl+scroll direction when changing the flashlight/highlight radius. Defaults to `true`. |

## Credit

Poomer is inspired by [tsoding/boomer](https://github.com/tsoding/boomer). This project is implemented in Python instead of Nim and keeps the main snapshot zoomer behavior; the experimental Nim compile-time features (`live`, `mitshm`, and `select`) are not ported.
