{
  description = "Greg podcast aggregator";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  };

  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-linux"
      ];

      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
          };

          python = pkgs.python313;

          pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
        in
        {
          default = python.pkgs.buildPythonApplication {
            pname = pyproject.project.name;
            version = pyproject.project.version;

            src = ./.;

            pyproject = true;

            build-system = [
              python.pkgs.uv-build
            ];

            dependencies = with python.pkgs; [
              feedparser
              requests
              eyed3
              beautifulsoup4
              lxml
            ];

            doCheck = false;
          };
        }
      );
    };
}
