# The images system-tests asks for, as `dockerTools.pullImage` tarballs (fixed-output fetches)
# tagged with the exact reference system-tests uses, so `ImageInfo.load` finds them with
# `images.get` and never pulls. Digests are system-tests' mirror_images.lock.yaml's, hashes
# ./lock/images.json's (`lock.py images`).
#
# Each image is fetched for the host's architecture, or for amd64 when it is published for amd64
# only (datadog/system-tests:proxy-v1, demisto/fastapi): on an arm64 host those run emulated (the
# daemon's kernel needs a binfmt_misc handler for x86_64, such as colima's Rosetta or qemu-user).
{
  lib,
  stdenv,
  dockerTools,
  lock,
}:
let
  hostArch = stdenv.hostPlatform.go.GOARCH;

  split =
    ref:
    let
      m = builtins.match "(.+):([^:/]+)" ref;
    in
    if m == null then
      {
        name = ref;
        tag = "latest";
      }
    else
      {
        name = builtins.elemAt m 0;
        tag = builtins.elemAt m 1;
      };

  pull =
    ref: entry:
    let
      inherit (split ref) name tag;
      arch = if entry.hashes ? ${hostArch} then hostArch else "amd64";
    in
    lib.extendDerivation true
      {
        inherit ref arch;
        emulated = arch != hostArch;
      }
      (
        dockerTools.pullImage {
          imageName = name;
          imageDigest = entry.digest;
          finalImageName = name;
          finalImageTag = tag;
          os = "linux";
          inherit arch;
          hash = entry.hashes.${arch};
        }
      );
in
{
  # reference -> image tarball.
  images = lib.mapAttrs pull lock.images;

  # SCENARIO -> variant -> the references it uses.
  inherit (lock) scenarios;
}
