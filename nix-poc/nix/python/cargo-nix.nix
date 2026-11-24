# Generates a crate2nix Cargo.nix for a Cargo workspace (import-from-derivation).
#
# crate2nix's own generatedCargoNix vendors git dependencies without resolving workspace
# inheritance (libdatadog's `edition.workspace = true`), which `cargo metadata` rejects, and
# hashes each git crate in a separate IFD step. Here cargo metadata runs against nixpkgs'
# importCargoLock vendor directory, which resolves inheritance, and the git hashes come from
# builtins.fetchGit's narHash at evaluation time: the same NAR hash the generated fetchgit calls
# (which fetch submodules) will produce.
{
  lib,
  runCommand,
  rustPlatform,
  cargo,
  crate2nix-cli,
  common,
}:
{
  name,
  # Directory with the workspace's Cargo.toml and Cargo.lock.
  src,
  # The same Cargo.lock, as a path readable at evaluation time.
  lockFile ? src + "/Cargo.lock",
}:
let
  lock = builtins.fromTOML (builtins.readFile lockFile);
  gitPackages = lib.filter (p: lib.hasPrefix "git+" (p.source or "")) lock.package;

  narHash =
    source:
    let
      m = builtins.match "git\\+([^?#]+)(\\?[^#]*)?#([0-9a-f]+)" source;
    in
    (builtins.fetchGit {
      url = builtins.elemAt m 0;
      rev = builtins.elemAt m 2;
      submodules = true;
    }).narHash;

  # crate2nix's crate-hashes.json keys: "<source without commit>#<name>@<version>".
  hashes = lib.listToAttrs (
    map (p: {
      name = "${builtins.head (lib.splitString "#" p.source)}#${p.name}@${p.version}";
      value = builtins.convertHash {
        hash = narHash p.source;
        toHashFormat = "nix32";
      };
    }) gitPackages
  );

  vendor = rustPlatform.importCargoLock {
    inherit lockFile;
    allowBuiltinFetchGit = true;
  };
in
runCommand "${name}-cargo-nix"
  (
    {
      nativeBuildInputs = [
        cargo
        crate2nix-cli
      ];
      passAsFile = [ "hashes" ];
      hashes = builtins.toJSON hashes;
    }
    // common.caAttrs
  )
  ''
    export HOME="$PWD" CARGO_HOME="$PWD/cargo-home" CARGO_NET_OFFLINE=true
    mkdir -p "$CARGO_HOME"
    sed 's|directory = "cargo-vendor-dir"|directory = "${vendor}"|' ${vendor}/.cargo/config.toml \
      > "$CARGO_HOME/config.toml"

    cp -r ${src} "$out"
    chmod -R u+w "$out"
    cd "$out"
    cp "$hashesPath" crate-hashes.json
    crate2nix generate -f ./Cargo.toml -o Cargo.nix -h crate-hashes.json
    echo 'import ./Cargo.nix' > default.nix
  ''
