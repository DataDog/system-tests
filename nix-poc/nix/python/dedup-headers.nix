# libdatadog's dedup_headers tool. setup.py `cargo install`s it from git at build time; here it is
# built with crate2nix from the libdatadog commit that src/native/Cargo.lock pins.
{
  pkgs,
  mkCargoNix,
  common,
  libdatadog-src,
}:
let
  crates = import (mkCargoNix {
    name = "libdatadog";
    src = libdatadog-src;
  }) {
    inherit pkgs;
    buildRustCrateForPkgs = pkgs: args: (pkgs.buildRustCrate args).overrideAttrs (_: common.caAttrs);
  };
in
crates.workspaceMembers.tools.build
