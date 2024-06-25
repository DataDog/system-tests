{
  description = "sys-tests";
  nixConfig.bash-prompt-prefix = "\[system-tests\] ";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    treefmt-nix.url = "github:numtide/treefmt-nix";

    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-24.05-darwin";
    nixpkgs-black-pinned.url = "github:NixOS/nixpkgs/6625284c397b44bc9518a5a1567c1b5aae455c08";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    treefmt-nix,
    nixpkgs-black-pinned,
  }: (flake-utils.lib.eachDefaultSystem (system: let
    pkgs-black = import nixpkgs-black-pinned {inherit system;};

    pinned-black = pkgs-black.black;

    black-overlay = final: prev: {
      black = pinned-black;
    };

    pkgs = import nixpkgs {
      inherit system;
      overlays = [
        black-overlay
      ];
    };

    black = pkgs.black;

    treefmt = treefmt-nix.lib.evalModule pkgs ./treefmt.nix;

    python = pkgs.python39;
  in {
    packages = {
      default = treefmt.config.build.wrapper;
      inherit black treefmt;
    };
    devShells.default =
      pkgs.mkShell
      {
        packages = [
          pkgs.curl
          pkgs.bash
          pkgs.coreutils
          pkgs.fswatch
          pkgs.rsync
          pkgs.shellcheck

          treefmt.config.build.wrapper
          python

          pkgs.ruff
        ];

        buildInputs = [python.pkgs.venvShellHook];
        venvDir = "./venv";

        postVenvCreation = ''
          unset SOURCE_DATE_EPOCH
          pip install -r requirements.txt
        '';
        postShellHook = ''
          unset SOURCE_DATE_EPOCH
          # hack: can't find libstdc++.so.8 otherwise
          # pawel: hack-disabled as this breaks everything on my system - since my gcc is newer than nixs
          # export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib"
        '';
      };

    formatter = treefmt.config.build.wrapper;
    checks = {
      formatting = treefmt.config.build.check self;
    };
  }));
}
