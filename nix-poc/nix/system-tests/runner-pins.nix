# Wheels for the system-tests runner's packages (./runner.nix) that nixpkgs lacks or ships
# with an incompatible API (see ./requirements-env.nix), and their dependencies nixpkgs lacks.
{
  ddapm-test-agent = {
    version = "1.18.0";
    hash = "sha256-2VpyPgkIFI9tRYj4JlNd4BKT3/+HZrAAG+TAm/JHAqQ=";
    dependencies = ps: [
      ps.aiohttp
      ps.ddsketch
      ps.msgpack
      ps.requests
      ps.typing-extensions
      ps.yarl
    ];
  };
  # nixpkgs' python pulumi-command is the provider plugin, not the Python SDK.
  pulumi-command = {
    version = "0.11.1";
    hash = "sha256-xYSj51eBgcik45OA8T8kOr4DbA9auTRkEShzn7wnI7o=";
    dependencies = ps: [
      ps.parver
      ps.pulumi
      ps.semver
    ];
  };
  pulumi-tls = {
    version = "5.0.3";
    hash = "sha256-st2BfW7inQHyTZyxgW20QA5z1btJqK2OrOO4NX59QHU=";
    dependencies = ps: [
      ps.parver
      ps.pulumi
      ps.semver
    ];
  };

  # 2.x renamed the module system-tests imports (yamlinclude).
  pyyaml-include = {
    version = "1.3";
    hash = "sha256-UUKgsPk9mx5YctWoFPNoH/vHBjgSjO0az9n7V9p4Jco=";
    dependencies = ps: [ ps.pyyaml ];
  };
  # ddapm-test-agent's, with the `serialization` extra it asks for.
  ddsketch = {
    version = "3.0.1";
    hash = "sha256-bQR7RV/ig3xD02b/Gua6DDFm4VSZ3oaIQ3p1zqkUIk4=";
    dependencies = ps: [
      ps.six
      ps.protobuf
    ];
  };
}
