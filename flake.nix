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
          runtimeLibs = with pkgs; [
            libGL
            libGLU
            xorg.libX11
            xorg.libXcursor
            xorg.libXext
            xorg.libXi
            xorg.libXinerama
            xorg.libXrandr
          ];
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.python312Packages.build
              pkgs.python312Packages.pip
            ] ++ runtimeLibs;

            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath runtimeLibs;
          };
        });
    };
}
