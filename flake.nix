{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/release-25.11";

    # cross-platform convenience
    flake-utils.url = "github:numtide/flake-utils";

    # backwards compatibility with nix-build and nix-shell
    flake-compat.url = "https://flakehub.com/f/edolstra/flake-compat/1.tar.gz";
  };

  outputs = { self, nixpkgs, flake-utils, flake-compat }:
    # resolve for all platforms in turn
    flake-utils.lib.eachDefaultSystem (system:
      let
        # packages for this system platform
        pkgs = nixpkgs.legacyPackages.${system};

        # control versions

        # get these python packages from nix
        python_packages = python-packages: [
          python-packages.pip
        ];

        # use this pyton version, and include the above packages
        python = pkgs.python312.withPackages python_packages;
      in {
        devShell = pkgs.stdenv.mkDerivation {
          name = "devshell";

          buildInputs = with pkgs; [
            # version to use + default packages are declared above
            python

            # linters
            shellcheck

            # for scripts
            bash
            fswatch
            rsync
          ] ++ lib.optionals (pkgs.stdenv.isDarwin) [
            # for python watchdog package
            apple-sdk
          ];

          shellHook = ''
            export PYTHON_VERSION="$(python -c 'import platform; import re; print(re.sub(r"\.\d+$", "", platform.python_version()))')"

            # replicate virtualenv behaviour
            export PIP_PREFIX="$PWD/vendor/python/$PYTHON_VERSION/packages"
            export PYTHONPATH="$PIP_PREFIX/lib/python$PYTHON_VERSION/site-packages:$PYTHONPATH"
            unset SOURCE_DATE_EPOCH
            export PATH="$PIP_PREFIX/bin:$PATH"

            # hack: can't find libstdc++.so.8 otherwise
            export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib"
          '';
        };
      }
    );
}
