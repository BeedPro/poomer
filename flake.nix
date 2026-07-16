{
  description = "Python development environment for poomer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python312.withPackages (ps: [
            ps.mss
            ps.pyglet
          ]);
          poomer = pkgs.writeShellApplication {
            name = "poomer";
            runtimeInputs = [ python ];
            text = ''
              PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}" exec python -m poomer "$@"
            '';
          };
          makeNixglPoomer = name: commandScript:
            pkgs.writeShellApplication {
              inherit name;
              runtimeInputs = [ python ];
              text = ''
                ${commandScript}

                printf '%s\n' "No nixGL wrapper found on PATH." >&2
                printf '%s\n' "Install nixGL for your distro/GPU, then retry this command." >&2
                exit 127
              '';
            };
          poomerNixgl = makeNixglPoomer "poomer-nixgl" ''
            if command -v nixGL >/dev/null 2>&1; then
              PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}" exec nixGL python -m poomer "$@"
            fi
            if command -v nixGLIntel >/dev/null 2>&1; then
              PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}" exec nixGLIntel python -m poomer "$@"
            fi
            if command -v nixGLNvidia >/dev/null 2>&1; then
              PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}" exec nixGLNvidia python -m poomer "$@"
            fi
          '';
          poomerNixglMesa = makeNixglPoomer "poomer-nixgl-mesa" ''
            if command -v nixGL >/dev/null 2>&1; then
              PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}" exec nixGL python -m poomer "$@"
            fi
            if command -v nixGLIntel >/dev/null 2>&1; then
              PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}" exec nixGLIntel python -m poomer "$@"
            fi
          '';
          poomerNixglNvidia = makeNixglPoomer "poomer-nixgl-nvidia" ''
            if command -v nixGLNvidia >/dev/null 2>&1; then
              PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}" exec nixGLNvidia python -m poomer "$@"
            fi
          '';
          runtimeLibs = with pkgs; [
            libGL
            libGLU
            libx11
            libxcursor
            libxext
            libxi
            libxinerama
            libxrandr
          ];
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              poomer
              poomerNixgl
              poomerNixglMesa
              poomerNixglNvidia
              pkgs.python312Packages.build
              pkgs.python312Packages.pip
            ] ++ runtimeLibs;

            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath runtimeLibs;
            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
            '';
          };
        });
    };
}
