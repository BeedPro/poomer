# Poomer

Python port of [tsoding/boomer](https://github.com/tsoding/boomer), a Linux screen zoomer.

## Quick Start

```console
$ python -m pip install -e .
$ poomer --help
$ poomer
```

## Dependencies

Poomer uses `pyglet` for the OpenGL window and `mss` for screen capture. On Debian-like systems you still need OpenGL/X11 runtime libraries installed.

```console
$ sudo apt-get install libgl1-mesa-dev libx11-dev libxext-dev libxrandr-dev
```
