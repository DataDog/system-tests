{
  description = "sys-tests";
  nixConfig.bash-prompt-prefix = "\[system-tests\] ";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    nix2containerPkg.url = "github:nlewo/nix2container";

    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-24.05-darwin";
    nixpkgs-black-pinned.url = "github:NixOS/nixpkgs/6625284c397b44bc9518a5a1567c1b5aae455c08";

    nix-github-actions.url = "github:nix-community/nix-github-actions";
    nix-github-actions.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    treefmt-nix,
    nix2containerPkg,
    nixpkgs-black-pinned,
    nix-github-actions,
  }:
    (flake-utils.lib.eachDefaultSystem (system: let
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

      nix2container = nix2containerPkg.packages.${system}.nix2container;

      pythonWithPkgs = pkgs.python39.withPackages (pythonPkgs:
        with pythonPkgs; [
          pip
          virtualenvwrapper
        ]);

      treefmt = treefmt-nix.lib.evalModule pkgs ./treefmt.nix;

      previewMarkdown = pkgs.writeScriptBin "preview" ''
        #!${pkgs.bash}/bin/bash
        ${pkgs.gh-markdown-preview}/bin/gh-markdown-preview "$@"
      '';

      devtools = pkgs.symlinkJoin {
        name = "devtools";
        paths = [
          pkgs.curl
          pkgs.bash
          pkgs.coreutils
          pkgs.fswatch
          pkgs.rsync
          pkgs.shellcheck
          pythonWithPkgs
          treefmt.config.build.wrapper
        ];
        postBuild = "echo links added";
      };
    in {
      packages = {
        default = devtools;

        inherit devtools previewMarkdown black;

        ### Build image usable in CI with dependencies
        ## nix run .#ciContainer.copyToDockerDaemon
        ## docker run --rm -it ci # to run the ci image
        ciContainer = nix2container.buildImage {
          name = "ci";
          tag = "latest";
          config = {
            entrypoint = ["/bin/bash"];
          };
          copyToRoot = pkgs.buildEnv {
            name = "root";
            paths = [
              devtools
            ];
            pathsToLink = ["/bin"];
          };
        };
      };
      devShells.default =
        pkgs.mkShell
        {
          packages = [
            devtools
          ];
          shellHook = ''
            export PYTHON_VERSION="$(python -c 'import platform; import re; print(re.sub(r"\.\d+$", "", platform.python_version()))')"

            # replicate virtualenv behaviour
            export PIP_PREFIX="$PWD/vendor/python/$PYTHON_VERSION/packages"
            export PYTHONPATH="$PIP_PREFIX/lib/python$PYTHON_VERSION/site-packages:$PYTHONPATH"
            unset SOURCE_DATE_EPOCH
            export PATH="$PIP_PREFIX/bin:$PATH"

            # hack: can't find libstdc++.so.8 otherwise
            # pawel: hack-disabled as this breaks everythin on my system
            # export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib"
          '';
        };

      formatter = treefmt.config.build.wrapper;
      checks = {
        formatting = treefmt.config.build.check self;
      };
    }))
    // {
      githubActions = nix-github-actions.lib.mkGithubMatrix {
        checks = {
          inherit (self.checks) x86_64-linux;
          x86_64-darwin = builtins.removeAttrs self.checks.x86_64-darwin ["formatting"];
        };
      };
    };
}
