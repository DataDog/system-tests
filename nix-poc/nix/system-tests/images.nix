# The non-weblog images a scenario starts, as image tarballs for `docker load`, each tagged with the
# reference system-tests asks for, so it uses the loaded image rather than pulling
# (TestedContainer.image.load). A run inside a Nix build has no network, so all of them come from
# the store. The scenario modules (./services) say which service runs which image.
#
#   agent, postgres   pinned upstream images. Digests are those of system-tests'
#                     mirror_images.lock.yaml, so `datadog/agent:latest` is whichever agent was
#                     latest when that lock was generated. To refresh one, take the digest from the
#                     lock file and get the hashes with
#                       nix-prefetch-docker --image-name <name> --image-tag <tag> \
#                         --image-digest <digest> --os linux --arch <arm64|amd64>
#   proxy             built here, in place of datadog/system-tests:proxy-v1 (amd64 only upstream)
#   internal-server   built here, in place of demisto/fastapi (amd64 only upstream)
#
# The built images hold no store paths, only the symlinks into the store their contents make:
# their services mount /nix/store read-only (nixStore in ./services), so loading them copies next
# to nothing. They only provide what the services' command and
# healthcheck need; the rest of the configuration comes from the scenario modules.
{
  lib,
  stdenv,
  dockerTools,
  python3,
  busybox,
  runner,
  systemTestsRoot,
}:
let
  goArch = stdenv.hostPlatform.go.GOARCH;

  pin =
    {
      name,
      tag,
      digest,
      hashes,
    }:
    dockerTools.pullImage {
      imageName = name;
      imageDigest = digest;
      finalImageName = name;
      finalImageTag = tag;
      os = "linux";
      arch = goArch;
      hash = hashes.${goArch};
    };

  # Built without store paths; `storePaths` is what they need from the store (the tarballs are
  # compressed, so they do not reference it themselves).
  storeless =
    args:
    lib.extendDerivation true { storePaths = args.contents; } (
      dockerTools.buildLayeredImage (args // { includeStorePaths = false; })
    );

  # ProxyContainer: `python -m proxy.core` in /app, with utils/proxy bind-mounted at /app/proxy.
  # core.py also reads the mitmproxy CA from /app/utils/proxy/.mitmproxy, which proxy.Dockerfile
  # copies into the image, so the same directory (from the same checkout as the tests) is copied
  # here, writable like in the Dockerfile's image. Its Python dependencies are all in the test
  # runner's environment (./runner.nix has mitmproxy for the proxy's sake).
  proxy = storeless {
    name = "datadog/system-tests";
    tag = "proxy-v1";
    contents = [
      runner.env
      busybox
    ];
    extraCommands = ''
      mkdir -p app/utils tmp
      chmod 1777 tmp
      cp -r --no-preserve=mode ${systemTestsRoot + "/utils/proxy"} app/utils/proxy
    '';
    config = {
      Cmd = [
        "python"
        "-m"
        "proxy.core"
      ];
      WorkingDir = "/app";
    };
  };

  # InternalServerContainer: `uvicorn app:app --port 8089` in /app with app.py bind-mounted, and a
  # `wget` healthcheck.
  internal-server = storeless {
    name = "demisto/fastapi";
    tag = "0.116.1.4266494";
    contents = [
      (python3.withPackages (ps: [
        ps.fastapi
        ps.uvicorn
      ]))
      busybox
    ];
    extraCommands = ''
      mkdir -p app tmp
      chmod 1777 tmp
    '';
    config.WorkingDir = "/app";
  };
in
{
  inherit proxy internal-server;

  agent = pin {
    name = "datadog/agent";
    tag = "latest";
    digest = "sha256:161a43ad2b290f7527a70e70c8880c1b3d65b39411552a8cb41398049546daf5";
    hashes = {
      arm64 = "sha256-oHhMDMA+qtlPugQXg85mu8lTYyAq8MRxQfbhp+dk8KE=";
      amd64 = "sha256-biXpz9LRZd6Nn1SHvYbmlaG09Q6B0GWLJ2M0EiDV734=";
    };
  };

  postgres = pin {
    name = "postgres";
    tag = "alpine";
    digest = "sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873";
    hashes = {
      arm64 = "sha256-/2inypFs85PZGwh0yfdH/8EVzDKOm9y60x7u6Pdh6IM=";
      amd64 = "sha256-YOa/roKslkf+0uJ+EwSttA/bnGXTvkGhpEAbRNdBGks=";
    };
  };
}
