# The test runner: what `./build.sh -i runner` puts in ./venv, a Python 3.12 venv with system-tests'
# requirements.txt installed, built from ./lock/runner.json (`lock.py runner`): every requirement
# and transitive dependency at the version uv resolved, as the wheel (or sdist) PyPI serves, pinned
# by hash. Nothing is taken from nixpkgs' Python package set but the build tools of the few sdists.
#
# Wheels are installed as published; on Linux, autoPatchelf points their native libraries at the
# store's libstdc++/zlib (manylinux wheels expect them on the system). Sdists (packages without a
# wheel for the platform, e.g. Brotli 1.0.9) are built each in their own derivation, without build
# isolation, with nixpkgs' setuptools/wheel/cython as the build backend.
{
  lib,
  stdenv,
  fetchurl,
  python312,
  autoPatchelfHook,
  zlib,
  lock,
}:
let
  python = python312;
  inherit (stdenv.hostPlatform) system;

  files =
    lock.platforms.${system}
      or (throw "system-tests-vanilla: the runner lock has no ${system}; regenerate it (lock.py runner)");

  buildPython = python.withPackages (ps: [
    ps.pip
    ps.setuptools
    ps.wheel
    ps.cython
  ]);

  fetch =
    f:
    fetchurl {
      inherit (f) url sha256;
      name = lib.strings.sanitizeDerivationName f.filename;
    };

  # name -> a directory holding the package's wheel, under its own file name.
  wheelDir =
    f:
    if f.kind == "wheel" then
      stdenv.mkDerivation {
        name = "${f.name}-${f.version}-wheel";
        dontUnpack = true;
        installPhase = ''
          mkdir $out
          ln -s ${fetch f} $out/${f.filename}
        '';
      }
    else
      stdenv.mkDerivation {
        name = "${f.name}-${f.version}-wheel";
        src = fetch f;
        dontUnpack = true;
        nativeBuildInputs = [ buildPython ];
        # No debug info: it would reference the compiler, and keep it in the runner's closure.
        env.CFLAGS = "-g0";
        env.CXXFLAGS = "-g0";
        buildPhase = ''
          export HOME=$TMPDIR
          cp $src ./${f.filename}
          python -m pip wheel --no-deps --no-build-isolation --no-index --wheel-dir $out ./${f.filename}
        '';
        dontInstall = true;
      };

  wheels = map wheelDir files;
in
stdenv.mkDerivation {
  name = "system-tests-runner-env";

  nativeBuildInputs = [ buildPython ] ++ lib.optional stdenv.hostPlatform.isLinux autoPatchelfHook;
  buildInputs = lib.optionals stdenv.hostPlatform.isLinux [
    stdenv.cc.cc.lib
    zlib
  ];

  dontUnpack = true;
  dontConfigure = true;
  dontBuild = true;
  # The wheels as published.
  dontStrip = true;

  installPhase = ''
    runHook preInstall
    export HOME=$TMPDIR
    ${python}/bin/python -m venv --without-pip $out
    python -m pip --python $out/bin/python install --no-index --no-deps --no-cache-dir \
      ${lib.concatMapStringsSep " " (w: "${w}/*.whl") wheels}
    # pip records where each wheel came from (file:// URLs into the store), which would keep every
    # wheel in the closure; installed from an index, as upstream does, there is no such file.
    find $out -name direct_url.json -delete
    runHook postInstall
  '';

  # manylinux wheels vendor what is not in the manylinux policy (<package>.libs, found through
  # $ORIGIN); libpython is the interpreter's, loaded already.
  autoPatchelfIgnoreMissingDeps = [ "libpython3*" ];

  passthru = {
    inherit python wheels;
    inherit (lock) requirementsSha256;
  };
}
