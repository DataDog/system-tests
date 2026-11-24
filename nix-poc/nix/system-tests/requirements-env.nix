# A Python environment of nixpkgs packages, by name. Every package is its own derivation: the
# nixpkgs package of that name or, when `pins` has a wheel for it, that wheel.
{ lib, fetchPypi }:
{
  python,
  # Package names, normalized like PyPI does (PEP 503).
  packages,
  # name -> { version, hash, python ? "py3", dependencies ? ps: [ ] }: published py3-none-any
  # wheels replacing the nixpkgs package of the same name in the whole package set. Dependencies
  # default to the nixpkgs package's; pythonRuntimeDepsCheck validates them against the wheel.
  pins ? { },
  # Further packageOverrides, applied before the pins.
  overrides ? _: _: { },
}:
let
  pinnedWheel =
    pyself: pysuper: name: pin:
    pyself.buildPythonPackage {
      pname = name;
      inherit (pin) version;
      format = "wheel";
      src = fetchPypi {
        pname = lib.replaceStrings [ "-" ] [ "_" ] name;
        inherit (pin) version hash;
        format = "wheel";
        dist = pin.python or "py3";
        python = pin.python or "py3";
      };
      dependencies =
        if pin ? dependencies then pin.dependencies pyself else pysuper.${name}.dependencies or [ ];
    };

  # The interpreter's package set with the pinned wheels substituted, so packages depending on
  # them see the pinned versions too.
  pinnedPython = python.override {
    self = pinnedPython;
    packageOverrides = lib.composeExtensions overrides (
      pyself: pysuper: lib.mapAttrs (pinnedWheel pyself pysuper) pins
    );
  };
  ps = pinnedPython.pkgs;

  package =
    name:
    ps.${name}
      or (throw "nix/system-tests: ${name} is not in nixpkgs; pin its wheel (see ./requirements-env.nix)");
in
{
  python = pinnedPython;
  env = pinnedPython.withPackages (_: map package packages);

  # name -> the version built.
  versions = lib.genAttrs packages (name: (package name).version);
}
