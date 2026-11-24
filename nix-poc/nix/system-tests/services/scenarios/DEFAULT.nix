# system-tests' DEFAULT scenario (utils/_context/_scenarios/default.py): the end-to-end services,
# plus Postgres and the internal server the weblog talks to.
{ images, ... }:
{
  imports = [ ../end-to-end.nix ];

  scenario = "DEFAULT";

  services = {
    weblog = {
      environment = {
        DD_DBM_PROPAGATION_MODE = "service";
        SOME_SECRET_ENV = "leaked-env-var"; # tests check that it is not leaked
        DD_EXTERNAL_ENV = "it-false,cn-weblog,pu-75a2b6d5-3949-4afb-ad0d-92ff0674e759";
        DD_TRACE_STATS_COMPUTATION_ENABLED = "false";
        DD_API_SECURITY_ENABLED = "false";
        DD_RUM_ENABLED = "true";
        DD_RUM_APPLICATION_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
        DD_RUM_CLIENT_TOKEN = "pubaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        DD_RUM_REMOTE_CONFIGURATION_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
        # The weblog's (main.py's) security controls.
        DD_IAST_SECURITY_CONTROLS_CONFIGURATION = builtins.concatStringsSep ";" [
          "SANITIZER:COMMAND_INJECTION:app:_sc_s_validate"
          "SANITIZER:*:app:_sc_s_validate_for_all"
          "SANITIZER:*:app:_sc_s_overloaded:0"
          "INPUT_VALIDATOR:COMMAND_INJECTION:app:_sc_v_validate"
          "INPUT_VALIDATOR:*:app:_sc_v_validate_for_all"
          "INPUT_VALIDATOR:*:app:_sc_v_overloaded:1,2"
        ];
      };
      dependsOn = [
        "postgres"
        "internal_server"
      ];
    };

    agent.environment.SOME_SECRET_ENV = "leaked-env-var";

    # PostgresContainer.
    postgres = {
      image = images.postgres;
      imageName = "postgres:alpine";
      user = "postgres";
      environment = {
        POSTGRES_PASSWORD = "password";
        PGPORT = "5433";
      };
      mounts."/docker-entrypoint-initdb.d/init_db.sh".source =
        "@tests@/utils/build/docker/postgres-init-db.sh";
      healthcheck = {
        test = "pg_isready -q -U postgres -d system_tests_dbname";
        retries = 30;
      };
    };

    # InternalServerContainer.
    internal_server = {
      image = images.internal-server;
      imageName = "demisto/fastapi:0.116.1.4266494";
      nixStore = true;
      workingDir = "/app";
      command = "uvicorn app:app --host 0.0.0.0 --port 8089";
      mounts."/app/app.py".source = "@tests@/utils/build/docker/internal_server/app.py";
      healthcheck = {
        test = "wget http://internal_server:8089";
        retries = 10;
      };
    };
  };
}
