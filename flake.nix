{
  description = "Python development environment for poomer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nixgl.url = "github:nix-community/nixGL";
  };

  outputs = { self, nixpkgs, nixgl }:
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
          makeNixglPoomer = name: nixglPackage:
            pkgs.writeShellApplication {
              inherit name;
              runtimeInputs = [ python ];
              text = ''
                if ! command -v nix >/dev/null 2>&1; then
                  printf '%s\n' "The nix command is required to launch ${name}." >&2
                  exit 127
                fi

                export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
                exec nix run --impure ${nixgl}#${nixglPackage} -- python -m poomer "$@"
              '';
            };
          poomerNixgl = makeNixglPoomer "poomer-nixgl" "nixGLDefault";
          poomerNixglMesa = makeNixglPoomer "poomer-nixgl-mesa" "nixGLDefault";
          poomerNixglNvidia = makeNixglPoomer "poomer-nixgl-nvidia" "nixGLNvidia";
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
