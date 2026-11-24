# What every end-to-end scenario runs (system-tests' EndToEndScenario with its defaults): the
# proxy, the agent and the weblog, as utils/_context/containers.py configures them for the Python
# library. Values are mkDefault: scenario modules override them with plain definitions.
#
# Mount sources under @tests@ are in the system-tests directory pytest runs in, the scenario's
# sources (../sources.nix, which they are added to), from the same checkout the weblog and the
# images are built from.
{
  lib,
  config,
  images,
  weblog,
  tufRoot,
  ...
}:
let
  inherit (lib) mkDefault mkOption types;
  cfg = config.endToEnd;

  # ProxyPorts (utils/proxy/ports.py).
  proxyPorts = {
    weblog = 8126;
    agent = 8200;
    commands = 11111;
  };
  agentPorts = {
    apmReceiver = 8127;
    dogstatsd = 8125;
  };
in
{
  options.endToEnd = {
    logs = mkOption {
      type = types.str;
      default = if config.scenario == "DEFAULT" then "logs" else "logs_${lib.toLower config.scenario}";
      description = "The scenario's log folder, relative to the system-tests directory (host_log_folder).";
    };
    appsec = mkOption {
      type = types.bool;
      default = true;
    };
    iast = mkOption {
      type = types.bool;
      default = true;
    };
  };

  # EndToEndScenario's components: the agent and the library.
  config.sources.manifests = [
    "agent"
    "python"
  ];
  # The JSON schemas payloads are validated against, which the validators
  # (tests/schemas/utils/schemas_validators.py) load at run time.
  config.sources.paths = [ "tests/schemas/utils" ];

  config.services = {
    proxy = {
      image = images.proxy;
      imageName = "datadog/system-tests:proxy-v1";
      nixStore = true;
      command = mkDefault "python -m proxy.core";
      workingDir = mkDefault "/app";
      environment = lib.mapAttrs (_: mkDefault) {
        # Unset: the run has no backend credentials (it is hermetic, see ../scenario.nix).
        DD_SITE = null;
        DD_API_KEY = null;
        DD_APP_KEY = null;
        SYSTEM_TESTS_IPV6 = "False";
        # The proxy writes "<this>/interfaces/...", which is also the path on the host.
        SYSTEM_TESTS_LOG_FOLDER = "./${cfg.logs}";
      };
      mounts = lib.mapAttrs (_: mkDefault) {
        "/app/proxy".source = "@tests@/utils/proxy";
        "/app/${cfg.logs}/interfaces" = {
          source = "@logs@/interfaces";
          readOnly = false;
        };
        # Written by system-tests (ProxyContainer.configure).
        "/app/logs/internal_mocked_tracer_responses.json".source =
          "@logs@/docker/proxy/internal_mocked_tracer_responses.json";
        "/app/logs/internal_mocked_backend_responses.json".source =
          "@logs@/docker/proxy/internal_mocked_backend_responses.json";
      };
      ports = mkDefault {
        "${toString proxyPorts.commands}/tcp" = [
          "127.0.0.1"
          proxyPorts.commands
        ];
      };
      healthcheck = mkDefault {
        test = "python -c \"import socket; s=socket.socket(socket.AF_INET); s.settimeout(2); s.connect(('localhost', ${toString proxyPorts.weblog})); s.close()\"";
        retries = 30;
      };
    };

    agent = {
      image = images.agent;
      imageName = "datadog/agent:latest";
      environment = lib.mapAttrs (_: mkDefault) {
        DD_ENV = "system-tests";
        DD_HOSTNAME = "test";
        DD_SITE = "datad0g.com";
        DD_APM_RECEIVER_PORT = toString agentPorts.apmReceiver;
        DD_DOGSTATSD_PORT = toString agentPorts.dogstatsd;
        DD_API_KEY = "0123456789abcdef0123456789abcdef"; # FakeDatadogKey.DEFAULT
        DD_PROXY_HTTPS = "http://proxy:${toString proxyPorts.agent}";
        DD_PROXY_HTTP = "http://proxy:${toString proxyPorts.agent}";
      };
      mounts = lib.mapAttrs (_: mkDefault) {
        # The mitmproxy CA (utils/proxy/.mitmproxy), so the agent trusts the proxy.
        "/etc/ssl/certs/ca-certificates.crt".source =
          "@tests@/utils/build/docker/agent/ca-certificates.crt";
        "/etc/datadog-agent/datadog.yaml".source = "@tests@/utils/build/docker/agent/datadog.yaml";
      };
      healthcheck = mkDefault {
        test = "curl --fail --silent --show-error --max-time 2 http://localhost:${toString agentPorts.apmReceiver}/info";
        retries = 60;
      };
      dependsOn = [ "proxy" ];
    };

    weblog = {
      image = weblog.storelessImage;
      imageName = "system_tests/weblog:latest";
      nixStore = true;
      # The image's app.sh, in its working directory (the weblog's app).
      command = mkDefault "./app.sh";
      environment = lib.mapAttrs (_: mkDefault) (
        {
          DD_SERVICE = "weblog";
          DD_VERSION = "1.0.0";
          DD_TAGS = "key1:val1,key2:val2";
          DD_ENV = "system-tests";
          DD_TRACE_LOG_DIRECTORY = "/var/log/system-tests";
          DD_RC_TUF_ROOT.file = tufRoot;
          DD_TELEMETRY_METRICS_ENABLED = "true";
          DD_TELEMETRY_HEARTBEAT_INTERVAL = "2";
          _DD_TELEMETRY_METRICS_ENABLED = "true";
          DD_TELEMETRY_METRICS_INTERVAL_SECONDS = "2";
          # The tracer sends to the proxy, which forwards to the agent.
          DD_AGENT_HOST = "proxy";
          DD_DOGSTATSD_HOST = "proxy";
          DD_TRACE_AGENT_PORT = toString proxyPorts.weblog;
          AWS_REGION = "us-east-1";
          AWS_DEFAULT_REGION = "us-east-1";
          AWS_SECRET_ACCESS_KEY = "not-secret";
          AWS_ACCESS_KEY_ID = "not-secret";
          DD_TRACE_HEADER_TAGS = "user-agent:http.request.headers.user-agent";
          DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS = "0.2";
        }
        # Which of the services the weblog can use the scenario runs (EndToEndWeblogInfra).
        // lib.mapAttrs (_: service: lib.boolToString (config.services ? ${service})) {
          INCLUDE_POSTGRES = "postgres";
          INCLUDE_CASSANDRA = "cassandra_db";
          INCLUDE_MONGO = "mongodb";
          INCLUDE_KAFKA = "kafka";
          INCLUDE_RABBITMQ = "rabbitmq";
          INCLUDE_MYSQL = "mysqldb";
          INCLUDE_SQLSERVER = "mssql";
        }
        // lib.optionalAttrs cfg.appsec {
          DD_APPSEC_ENABLED = "true";
          DD_APPSEC_WAF_TIMEOUT = "10000000"; # 10 seconds
          DD_APPSEC_TRACE_RATE_LIMIT = "10000";
        }
        // lib.optionalAttrs cfg.iast {
          DD_IAST_ENABLED = "true";
          _DD_IAST_DEBUG = "true";
          DD_IAST_REQUEST_SAMPLING = "100";
          DD_IAST_MAX_CONCURRENT_REQUESTS = "10";
          DD_IAST_DEDUPLICATION_ENABLED = "false";
          DD_IAST_VULNERABILITIES_PER_REQUEST = "10";
          DD_IAST_MAX_CONTEXT_OPERATIONS = "10";
        }
      );
      mounts."/var/log/system-tests" = mkDefault {
        source = "@logs@/docker/weblog/logs";
        readOnly = false;
      };
      ports = mkDefault {
        "7777/tcp" = 7777;
        "7778/tcp" = 7778; # gRPC
      };
      healthcheck = mkDefault {
        test = "curl --fail --silent --show-error --max-time 2 localhost:7777/healthcheck";
        retries = 60;
      };
      # ddprof's perf_event_open is blocked by Docker's default seccomp profile.
      securityOpt = mkDefault [ "seccomp=unconfined" ];
      # py-spy dumps the weblog's stacks when a remote config apply stalls (utils/_remote_config.py).
      capAdd = mkDefault [ "SYS_PTRACE" ];
      dependsOn = [
        "agent"
        "proxy"
      ];
    };
  };
}
