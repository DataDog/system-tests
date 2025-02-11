# treefmt.nix
{
  pkgs,
  lib,
  ...
}: {
  # Used to find the project root
  projectRootFile = "flake.nix";
  # Enable the Nix formatter "alejandra"
  programs.alejandra.enable = true;
  # Format py sources
  programs.black.enable = true;
  # Format .sh scripts
  # programs.shfmt.enable = true;

  programs.shellcheck.enable = true;

  settings.formatter.shellcheck = {
    excludes = [
      # TODO: scripts to fix
      "utils/scripts/load-binary.sh"
      "utils/scripts/install_mitm_certificate.sh"
      "utils/scripts/update_dashboard_CI_visibility.sh"
      "utils/scripts/slack/report.sh"
      "utils/scripts/docker_base_image.sh"
      "utils/scripts/upload_results_CI_visibility.sh"
      "utils/build/docker/postgres-init-db.sh"
      "utils/build/docker/nodejs/app.sh"
      "utils/build/docker/nodejs/install_ddtrace.sh"
      "utils/build/docker/set-uds-transport.sh"
      "utils/build/docker/python/flask/app.sh"
      "utils/build/docker/python/install_ddtrace.sh"
      "utils/build/docker/python/django/app.sh"
      "utils/build/docker/golang/app.sh"
      "utils/build/docker/golang/install_ddtrace.sh"
      "utils/build/docker/weblog-cmd.sh"
      "utils/build/docker/java/app.sh"
      "utils/build/docker/java/install_ddtrace.sh"
      "utils/build/docker/java/spring-boot/app.sh"
      "utils/build/docker/php/apache-mod/build.sh"
      "utils/build/docker/php/apache-mod/entrypoint.sh"
      "utils/build/docker/php/php-fpm/build.sh"
      "utils/build/docker/php/php-fpm/entrypoint.sh"
      "utils/build/docker/php/common/install_ddtrace.sh"
      "utils/build/docker/dotnet/app.sh"
      "utils/build/docker/dotnet/install_ddtrace.sh"
      "utils/build/docker/cpp/install_ddprof.sh"
      "utils/build/docker/cpp/nginx/app.sh"
      "utils/build/docker/cpp/nginx/install_ddtrace.sh"
      "utils/build/docker/ruby/install_ddtrace.sh"
      "utils/build/build.sh"
      "utils/interfaces/schemas/serve.sh"
      "build.sh"
      # "format.sh"

      # ignored paths
      "tests/perfs/*.sh"
      "parametric/*.sh"
      "lib-injection/*.sh"
    ];
  };

  settings.formatter.whitespace = {
    command = "${pkgs.bash}/bin/bash";
    options = [
      "-euc"
      ''
        ${pkgs.gnused}/bin/sed -i -r 's/ +$//g' "$@"
      ''
      "--"
    ];
    includes = ["*.md" "*.yml" "*.yaml" "*.sh" "*.cs" "*.Dockerfile" "*.java" "*.sql" "*.ts" "*.js" "*.php"];
    excludes = ["logs*" "./manifests/*" "./utils/build/virtual_machine/*"];

    settings.global.excludes = ["./venv/*" "*/node_modules/*" "tests/appsec/waf/blocked*" "utils/parametric/protos/*.py"];
  };

  settings.global.excludes = ["tests/fuzzer/**" "tests/appsec/waf/blocked*" "utils/parametric/protos/*.py"];
}
