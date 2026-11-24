# system-tests' Python fastapi weblog, built natively with Nix: the application code comes from
# the system-tests checkout, everything else (interpreter, packages, environment, image) is
# declared here. Package versions are nixpkgs', not the pins of system-tests' requirements file.
#
#   app       the weblog's files from system-tests, byte-compiled, and app.sh running `command`
#   env       python.withPackages: ddtrace from this build + the packages the app imports
#   launcher  bin/weblog: `environment` as defaults, then app.sh
#   image     OCI image for `docker load` (Linux only)
#   storelessImage  the same without its store paths, for containers mounting /nix/store
#   imports   check: the app's modules import in `env`
{
  lib,
  stdenv,
  runCommand,
  dockerTools,
  fetchPypi,
  py-spy,
  bash,
  coreutils,
  curl,
  cacert,
  common,
  systemTestsRoot,
  python,
  python-package,
}:
let
  variant = "fastapi";
  weblogDir = systemTestsRoot + "/utils/build/docker/python";

  # The weblog's files, at the paths the app expects relative to its working directory.
  appFiles = {
    "main.py" = weblogDir + "/fastapi/main.py";
    "iast.py" = weblogDir + "/iast.py";
    "log_conf.yaml" = weblogDir + "/fastapi/log_conf.yaml";
  };

  # Defaults for the weblog process. system-tests sets more on the container, and its values win.
  environment = {
    DD_TRACE_HEADER_TAGS = "user-agent:http.request.headers.user-agent";
    DD_REMOTECONFIG_POLL_SECONDS = "1";
    _DD_APPSEC_DEDUPLICATION_ENABLED = "false";
    DD_CODE_ORIGIN_FOR_SPANS_ENABLED = "0";
  };

  # Not in nixpkgs. Pure Python, no dependencies.
  openfeature-sdk = python.pkgs.buildPythonPackage rec {
    pname = "openfeature-sdk";
    version = "0.8.3";
    format = "wheel";
    src = fetchPypi {
      pname = "openfeature_sdk";
      inherit version format;
      dist = "py3";
      python = "py3";
      hash = "sha256-KOgXUUxTmOIkPQoVjzMGYkODdXuoMwMjNs66Kzy83dY=";
    };
  };

  # Stripe objects stopped being dicts in later versions (nixpkgs has 15), and main.py's webhook
  # endpoint returns one through JSONResponse, failing the payment events tests with a 403.
  stripe = python.pkgs.stripe.overridePythonAttrs rec {
    version = "13.2.0";
    format = "wheel";
    pyproject = null;
    src = fetchPypi {
      pname = "stripe";
      inherit version format;
      dist = "py3";
      python = "py3";
      hash = "sha256-59GL1EurGBK8Tp512kzqzt1Yf3Fze7kZOVXt9CBgX4g=";
    };
    doCheck = false;
  };

  env = python.withPackages (ps: [
    python-package # ddtrace
    # The web stack: main.py, log_conf.yaml, `uvicorn --loop uvloop`.
    ps.fastapi
    ps.starlette
    ps.uvicorn
    ps.uvloop
    ps.anyio
    ps.pydantic
    ps.python-multipart # Form()
    ps.itsdangerous # SessionMiddleware
    ps.pyyaml
    # Imported by main.py and iast.py.
    ps.jinja2
    ps.packaging
    ps.psycopg2
    ps.pycryptodome
    ps.requests
    stripe
    ps.xmltodict
    openfeature-sdk # ddtrace.openfeature
    ps.opentelemetry-exporter-otlp-proto-http # ddtrace's feature flag metrics
  ]);

  # system-tests starts the weblog container with `./app.sh` (WeblogContainer), whatever its Cmd.
  app =
    runCommand "system-tests-weblog-${variant}-app"
      (
        {
          nativeBuildInputs = [ python ];
        }
        // common.caAttrs
      )
      ''
        mkdir -p "$out"
        ${lib.concatStrings (
          lib.mapAttrsToList (name: src: ''
            cp ${src} "$out/${name}"
          '') appFiles
        )}
        cat > "$out/app.sh" <<'EOF'
        #!${bash}/bin/bash
        exec ${lib.escapeShellArgs command} "$@"
        EOF
        chmod +x "$out/app.sh"
        # The store is read-only at run time, so compile ahead of time. Hash-based .pyc files stay
        # valid regardless of file timestamps.
        python -m compileall -q --invalidation-mode checked-hash "$out"
      '';

  sitePackages = "${env}/${env.sitePackages}";

  path = lib.makeBinPath [
    env
    py-spy # system-tests dumps the weblog's stacks with it (utils/_remote_config.py)
    bash
    coreutils
    curl
  ];

  # ddtrace-run puts its own sitecustomize first on PYTHONPATH, which shadows the one Nix Python
  # environments use to find their packages from wrapped programs (uvicorn).
  runtimeEnv = environment // {
    PATH = path;
    PYTHONPATH = sitePackages;
  };

  command = [
    "ddtrace-run"
    "uvicorn"
    "main:app"
    "--host"
    "0.0.0.0"
    "--port"
    "7777"
    "--loop"
    "uvloop"
    "--log-config=log_conf.yaml"
  ];

  launcher =
    runCommand "system-tests-weblog-${variant}"
      (
        {
          passthru = {
            inherit
              app
              env
              variant
              imports
              ;
          }
          // lib.optionalAttrs stdenv.hostPlatform.isLinux { inherit image storelessImage; };
          meta.mainProgram = "weblog";
        }
        // common.caAttrs
      )
      ''
        mkdir -p "$out/bin"
        cat > "$out/bin/weblog" <<'EOF'
        #!${bash}/bin/bash
        set -eu
        export PATH=${path}''${PATH:+:$PATH}
        export PYTHONPATH=${sitePackages}''${PYTHONPATH:+:$PYTHONPATH}
        ${lib.concatStrings (
          lib.mapAttrsToList (name: value: ''
            [ -n "''${${name}+set}" ] || export ${name}=${lib.escapeShellArg value}
          '') environment
        )}
        cd ${app}
        exec ./app.sh "$@"
        EOF
        chmod +x "$out/bin/weblog"
      '';

  # Fails when the app imports a module `env` lacks, e.g. after system-tests adds a dependency.
  imports =
    runCommand "system-tests-weblog-${variant}-imports"
      {
        nativeBuildInputs = [ env ];
        DD_TRACE_ENABLED = "false";
        DD_INSTRUMENTATION_TELEMETRY_ENABLED = "false";
        DD_REMOTE_CONFIGURATION_ENABLED = "false";
      }
      ''
        cd ${app}
        HOME="$TMPDIR" python -c 'import main' > "$out"
      '';

  imageContents = [
    bash
    coreutils
    curl # healthcheck
    cacert
    dockerTools.binSh
    dockerTools.usrBinEnv
  ];

  imageArgs = {
    name = "system_tests/weblog";
    tag = "latest";
    contents = imageContents;
    extraCommands = ''
      mkdir -p -m 1777 tmp
    '';
    config = {
      Cmd = [ "./app.sh" ];
      WorkingDir = "${app}";
      Env = lib.mapAttrsToList (n: v: "${n}=${v}") (
        runtimeEnv
        // {
          PATH = "${path}:/bin";
          SSL_CERT_FILE = "${cacert}/etc/ssl/certs/ca-bundle.crt";
        }
      );
      ExposedPorts."7777/tcp" = { };
      # What system-tests reads to identify the weblog (utils/build/build.sh sets the same labels).
      Labels = {
        "system-tests-library" = "python";
        "system-tests-weblog-variant" = variant;
      };
    };
  };

  # Self-contained, for `docker load` anywhere (e.g. system-tests' own ./run.sh).
  image = dockerTools.streamLayeredImage imageArgs;

  # Without the store paths, for containers that mount /nix/store (the scenarios of ./services):
  # a few KiB to load. The store paths it needs are in `storePaths`, for whatever references it to
  # keep them (the tarball is compressed, so it does not reference them itself).
  storelessImage = lib.extendDerivation true { storePaths = imageContents ++ [ launcher ]; } (
    dockerTools.buildLayeredImage (imageArgs // { includeStorePaths = false; })
  );
in
launcher
