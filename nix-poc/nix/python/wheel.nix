# The wheel: a merge of every tree, plus WHEEL / RECORD written by `wheel pack`.
{
  lib,
  stdenvNoCC,
  common,
  python,
  python-sources,
  dist-info,
  libddwaf,
  native,
  profiling,
  iast,
  extensions,
}:
let
  trees = [
    python-sources
    libddwaf
    native.module
    iast
  ]
  ++ lib.attrValues extensions.modules
  ++ lib.optionals native.profiling [
    profiling.dd-wrapper
    profiling.ddup
    profiling.stack
    profiling.memalloc
  ];
in
stdenvNoCC.mkDerivation (
  {
    pname = "ddtrace-wheel";
    inherit (common) version;

    dontUnpack = true;
    dontConfigure = true;
    dontFixup = true;

    nativeBuildInputs = [ (python.withPackages (ps: [ ps.wheel ])) ];

    passthru = { inherit trees; };

    buildPhase = ''
      runHook preBuild
      mkdir staging
      ${lib.concatMapStrings (tree: ''
        cp -rT --no-preserve=mode ${tree} staging
      '') trees}
      cp -r --no-preserve=mode ${dist-info}/*.dist-info staging/

      tag="$(python - <<'EOF'
      import sys, sysconfig
      impl = "cp%d%d" % sys.version_info[:2]
      abi = impl + ("t" if sysconfig.get_config_var("Py_GIL_DISABLED") else "")
      print("-".join([impl, abi, sysconfig.get_platform().replace("-", "_").replace(".", "_")]))
      EOF
      )"
      distInfo="$(echo staging/*.dist-info)"
      printf 'Wheel-Version: 1.0\nGenerator: ddtrace-nix\nRoot-Is-Purelib: false\nTag: %s\n' "$tag" \
        > "$distInfo/WHEEL"

      mkdir -p "$out"
      python -m wheel pack staging --dest-dir "$out"
      runHook postBuild
    '';

    dontInstall = true;
  }
  // common.caAttrs
)
