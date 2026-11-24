# Helpers shared by every derivation, plus the pins this build reads from the repository so they are
# never duplicated in Nix: the package version, the libddwaf release and checksums, the abseil commit
# and the libdatadog commit.
{
  lib,
  root,
  contentAddressed,
}:
let
  readLines = path: lib.splitString "\n" (builtins.readFile path);

  # First capture group of the first line in path matching regex.
  grepFirst =
    path: regex:
    let
      matches = lib.filter (m: m != null) (map (builtins.match regex) (readLines path));
    in
    if matches == [ ] then
      throw "nix/python/common.nix: no line in ${toString path} matches ${regex}"
    else
      builtins.head (builtins.head matches);

  setupPy = root + "/setup.py";
  pyproject = builtins.fromTOML (builtins.readFile (root + "/pyproject.toml"));
  cargoLock = builtins.fromTOML (builtins.readFile (root + "/src/native/Cargo.lock"));

  libdatadogSource =
    (lib.findFirst (p: p.name == "libdd-common") (throw "libdd-common missing from Cargo.lock") cargoLock.package)
    .source;
in
rec {
  inherit (pyproject.project) version;
  pname = pyproject.project.name;

  # Content addressing is what turns "this input changed" into "only rebuild what actually differs":
  # when a derivation reproduces a byte-identical output, every dependent derivation keeps its
  # store path and is not rebuilt. Fixed-output fetchers are content addressed already.
  caAttrs = lib.optionalAttrs contentAddressed {
    __contentAddressed = true;
    outputHashMode = "recursive";
    outputHashAlgo = "sha256";
  };

  # Source trees are filtered down to exactly the files each step reads, so unrelated edits never
  # change a derivation's inputs in the first place.
  src =
    files:
    lib.fileset.toSource {
      inherit root;
      fileset = lib.fileset.unions files;
    };

  # Debug info is stripped from everything under ddtrace/, like the release wheels.
  stripDebugList = [ "ddtrace" ];

  libddwaf = rec {
    version = grepFirst setupPy ''LIBDDWAF_VERSION = "([^"]+)".*'';
    checksum = archive: grepFirst setupPy ''.*"${lib.escapeRegex archive}": "([0-9a-f]{64})".*'';
  };

  abseil = {
    rev = grepFirst (root + "/cmake/abseil/CMakeLists.txt") ''.*GIT_TAG ([0-9a-f]{40}).*'';
    tag = grepFirst (root + "/cmake/abseil/CMakeLists.txt") ''.*# tag ([^ ]+)'';
  };

  libdatadog = {
    url = builtins.head (builtins.match "git\\+([^?]+)\\?.*" libdatadogSource);
    rev = builtins.head (builtins.match ".*#([0-9a-f]{40})" libdatadogSource);
  };

  # Shell snippet exporting the interpreter facts that name extension modules.
  pythonVars = python: ''
    export EXT_SUFFIX="$(${python.interpreter} -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')"
    export PY_MAJMIN="$(${python.interpreter} -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  '';
}
