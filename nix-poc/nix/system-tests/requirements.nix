# Pins of a requirements file (system-tests' requirements.txt), for comparing them with what the
# runner builds (see ./runner.nix, versionDrift): a list of { name, version }, comments and blank
# lines skipped. Nothing is built from it.
{ lib }:
let
  # "name==version" -> { name, version }, with the name normalized like PyPI does (PEP 503).
  parseRequirement =
    spec:
    let
      m = builtins.match "([A-Za-z0-9._-]+)==([^ ;]+).*" spec;
    in
    if m == null then
      throw "nix/system-tests: only exact pins (name==version) are supported, got '${spec}'"
    else
      {
        name = lib.toLower (lib.replaceStrings [ "_" "." ] [ "-" "-" ] (builtins.elemAt m 0));
        version = builtins.elemAt m 1;
      };
in
path:
map parseRequirement (
  lib.filter (l: l != "") (
    map (l: lib.trim (builtins.head (lib.splitString "#" l))) (
      lib.splitString "\n" (builtins.readFile path)
    )
  )
)
