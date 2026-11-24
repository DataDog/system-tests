# The prebuilt libddwaf release that setup.py downloads, verified against the checksums pinned in
# setup.py, laid out where the wheel expects it.
{
  lib,
  stdenv,
  fetchurl,
  common,
}:
let
  inherit (stdenv.hostPlatform) system;
  # system -> [ directory name setup.py uses, archive platform suffix, library suffix ]
  platforms = {
    x86_64-linux = [ "x86_64" "x86_64-linux-musl" ".so" ];
    aarch64-linux = [ "aarch64" "aarch64-linux-musl" ".so" ];
    x86_64-darwin = [ "x86_64" "darwin-x86_64" ".dylib" ];
    aarch64-darwin = [ "arm64" "darwin-arm64" ".dylib" ];
  };
  platform = platforms.${system} or (throw "libddwaf: unsupported system ${system}");
  arch = builtins.elemAt platform 0;
  archive = "libddwaf-${common.libddwaf.version}-${builtins.elemAt platform 1}.tar.gz";
  suffix = builtins.elemAt platform 2;
in
stdenv.mkDerivation (
  {
    pname = "ddtrace-libddwaf";
    inherit (common.libddwaf) version;

    src = fetchurl {
      url = "https://github.com/DataDog/libddwaf/releases/download/${common.libddwaf.version}/${archive}";
      sha256 = common.libddwaf.checksum archive;
    };

    dontConfigure = true;
    dontBuild = true;
    # Shipped as released, like the upstream wheels.
    dontFixup = true;

    installPhase = ''
      runHook preInstall
      dest=$out/ddtrace/appsec/_ddwaf/libddwaf/${arch}/lib
      mkdir -p "$dest"
      for name in libddwaf${suffix} ddwaf${suffix}; do
        if [ -e "lib/$name" ]; then
          cp "lib/$name" "$dest/libddwaf${suffix}"
        fi
      done
      test -e "$dest/libddwaf${suffix}"
      runHook postInstall
    '';
  }
  // common.caAttrs
)
