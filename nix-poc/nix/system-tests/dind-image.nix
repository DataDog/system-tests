# The pinned docker:dind image scenario runs happen in (./dind-run.nix is its entrypoint), as an
# image tarball for `docker load`.
{ stdenv, dockerTools }:
let
  goArch = stdenv.hostPlatform.go.GOARCH;
in
dockerTools.pullImage {
  imageName = "docker";
  imageDigest = "sha256:2a232a42256f70d78e3cc5d2b5d6b3276710a0de0596c145f627ecfae90282ac";
  finalImageName = "docker";
  finalImageTag = "28-dind";
  os = "linux";
  arch = goArch;
  hash =
    {
      arm64 = "sha256-pEJsyuMquWysn3ZFF/E97XUZWvh59iyGGONlgDyemiI=";
      amd64 = "sha256-1/tNhXbG/568/OHM2Sq4/5vkpltgmZpMC64gjYBvOns=";
    }
    .${goArch};
}
