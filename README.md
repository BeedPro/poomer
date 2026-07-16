# Poomer

Python screen zoomer inspired by the original Nim implementation.

## Quick Start

```console
$ python -m pip install -e .
$ poomer --help
$ poomer
```

With Nix flakes:

```console
$ nix develop
$ poomer --help
$ poomer
```

## Dependencies

Poomer uses `pyglet` for the OpenGL window and `mss` for screen capture. On Debian-like systems you still need OpenGL/X11 runtime libraries installed.

```console
$ sudo apt-get install libgl1-mesa-dev libx11-dev libxext-dev libxrandr-dev
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

## Credit

Poomer is inspired by [tsoding/boomer](https://github.com/tsoding/boomer). This project is implemented in Python instead of Nim and keeps the main snapshot zoomer behavior; the experimental Nim compile-time features (`live`, `mitshm`, and `select`) are not ported.
