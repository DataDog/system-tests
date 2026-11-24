# The system-tests test runner (what `./build.sh -i runner` puts in ./venv): a Python environment
# declared here, nixpkgs packages with the wheels of ./runner-pins.nix where nixpkgs has none or an
# incompatible one. Shared by every scenario, weblog and interpreter. system-tests'
# requirements.txt is not built from; `versionDrift` compares the two.
{
  lib,
  callPackage,
  python312,
  systemTestsRoot,
}:
let
  # What running the tests imports: the framework and the tests (pytest and its plugins, the
  # proxy, the mocked backend, payload decoding and validation) and, since system-tests' scenario
  # definitions all load with it, what every scenario's code imports at module level (docker,
  # kubernetes, pulumi, paramiko, ...).
  packages = [
    # pytest and the plugins system-tests' pyproject.toml and conftest.py use.
    "pytest"
    "pytest-json-report"
    "pytest-timeout"
    "pytest-xdist"
    "pluggy"

    # The proxy (utils/proxy), the mocked backend (utils/mocked_backend) and payload decoding.
    "mitmproxy"
    "aiohttp"
    "aiofiles"
    "brotli"
    "zstandard"
    "msgpack"
    "requests"
    "requests-toolbelt"
    "yarl"
    "opentelemetry-api"
    "opentelemetry-proto"
    "pynacl" # TUF signing in the remote config mocks

    # Validation and the framework's helpers.
    "jsonschema"
    "rfc3339-validator"
    "pyyaml"
    "pyyaml-include"
    "jinja2"
    "semantic-version"
    "python-dateutil"
    "dictdiffer"
    "filelock"
    "psutil"
    "retry"
    "watchdog"
    "numpy"
    "pygtrie"
    "mock"
    "ddapm-test-agent"

    # Containers, clusters and virtual machines (docker-based scenarios, Kubernetes, onboarding).
    "docker"
    "kubernetes"
    "boto3"
    "paramiko"
    "scp"
    "pexpect"
    "crossplane"
    "python-vagrant"
    "pulumi"
    "pulumi-aws"
    "pulumi-command"
    "pulumi-tls"
  ];

  # requirements.txt entries not installed: linters, type checkers and their stubs, build and CI
  # tooling (pytest-split splits test runs across CI jobs; requires pytest < 9).
  notInstalled = [
    "import-linter"
    "mypy"
    "ruff"
    "shellcheck-py"
    "yamllint"
    "setuptools"
    "uv"
    "pytest-split"
  ];

  built = callPackage ./requirements-env.nix { } {
    # pyproject.toml's mypy python_version, and the runner image's base (python:3.12).
    python = python312;
    inherit packages;
    pins = import ./runner-pins.nix;
    overrides = pyself: pysuper: {
      # mitmproxy's dependency. tests/block/test_block_2.py allocates buffers of several GiB,
      # more than a small Linux builder (colima's VM) has.
      lz4 = pysuper.lz4.overridePythonAttrs { doCheck = false; };
      # Expects a mode-0 directory not to be searchable, which it is for root: linux-nix
      # (./linux-nix.nix) builds as root.
      aiofiles = pysuper.aiofiles.overridePythonAttrs (old: {
        disabledTestPaths = (old.disabledTestPaths or [ ]) ++ [ "tests/test_os.py::test_access" ];
      });
      # Times two concurrent 0.5 s hooks against wall-clock bounds, which a loaded builder (a cold
      # build runs many in parallel) misses.
      mitmproxy = pysuper.mitmproxy.overridePythonAttrs (old: {
        disabledTestPaths = (old.disabledTestPaths or [ ]) ++ [
          "test/mitmproxy/script/test_concurrent.py::TestConcurrent::test_concurrent"
        ];
      });
      # Its tests bind 127.0.0.1:4317, which collides with anything listening there when builds
      # are not sandboxed (the default on macOS). nixpkgs only provides opentelemetry-sdk, a
      # runtime dependency, to the tests.
      opentelemetry-exporter-otlp-proto-grpc =
        pysuper.opentelemetry-exporter-otlp-proto-grpc.overridePythonAttrs
          (old: {
            doCheck = false;
            dependencies = old.dependencies ++ [ pyself.opentelemetry-sdk ];
          });
    };
  };
in
{
  inherit (built) env;

  # Where the runner and system-tests' requirements.txt disagree: name -> { wanted, built }, with
  # `wanted` the pin (null: not in requirements.txt) and `built` the version built (null: not
  # installed). Linters, type stubs and notInstalled are left out. Evaluation only: reading
  # requirements.txt here does not make anything depend on it.
  versionDrift =
    let
      upstream = lib.filter (r: !(lib.elem r.name notInstalled || lib.hasPrefix "types-" r.name)) (
        callPackage ./requirements.nix { } (systemTestsRoot + "/requirements.txt")
      );
      wanted = lib.listToAttrs (map (r: lib.nameValuePair r.name r.version) upstream);
    in
    lib.filterAttrs (_: d: d.wanted != d.built) (
      lib.genAttrs (lib.unique (lib.attrNames wanted ++ packages)) (name: {
        wanted = wanted.${name} or null;
        built = built.versions.${name} or null;
      })
    );

  # The checkout, minus what no test run reads: what ./sources.nix takes each scenario's sources
  # from.
  checkout = lib.fileset.toSource {
    root = systemTestsRoot;
    fileset = lib.fileset.difference systemTestsRoot (
      lib.fileset.unions [
        (lib.fileset.maybeMissing (systemTestsRoot + "/binaries"))
        (lib.fileset.maybeMissing (systemTestsRoot + "/docs"))
        (lib.fileset.maybeMissing (systemTestsRoot + "/lib-injection"))
      ]
    );
  };
}
