# The libdatadog C headers (common.h, profiling.h) that the profiling C++ code includes. setup.py
# gets them as a side effect of libdatadog's cbindgen build scripts; here cbindgen runs on the
# libdatadog workspace directly, with the same configuration, and dedup_headers then moves the
# shared definitions into common.h as setup.py does. Independent of Python and of src/native's
# own code, so it is built once and survives Rust edits.
{
  lib,
  stdenvNoCC,
  cargo,
  rust-cbindgen,
  rustPlatform,
  common,
  libdatadog-src,
  dedup-headers,
}:
let
  vendor = rustPlatform.importCargoLock {
    lockFile = libdatadog-src + "/Cargo.lock";
    allowBuiltinFetchGit = true;
  };
  headers = {
    "libdd-common-ffi" = "common.h";
    "libdd-profiling-ffi" = "profiling.h";
  };
in
stdenvNoCC.mkDerivation (
  {
    pname = "ddtrace-native-headers";
    version = builtins.substring 0 12 common.libdatadog.rev;

    src = libdatadog-src;

    nativeBuildInputs = [
      cargo
      rust-cbindgen
      dedup-headers
    ];

    dontConfigure = true;
    dontFixup = true;

    buildPhase = ''
      runHook preBuild
      export CARGO_HOME="$NIX_BUILD_TOP/cargo-home" CARGO_NET_OFFLINE=true
      mkdir -p "$CARGO_HOME" "$out/datadog"
      sed 's|directory = "cargo-vendor-dir"|directory = "${vendor}"|' ${vendor}/.cargo/config.toml \
        > "$CARGO_HOME/config.toml"
      ${lib.concatStrings (
        lib.mapAttrsToList (crate: header: ''
          cbindgen --config ${crate}/cbindgen.toml --output "$out/datadog/${header}" ${crate}
        '') headers
      )}
      (cd "$out/datadog" && dedup_headers common.h profiling.h)
      runHook postBuild
    '';

    dontInstall = true;
  }
  // common.caAttrs
)
