{
  perSystem =
    { self', ... }:
    let
      ddtrace = self'.legacyPackages;
    in
    {
      packages = {
        default = ddtrace.wheel;
        inherit (ddtrace) wheel python-package;
        weblog-fastapi = ddtrace.weblogs.fastapi;
        # system-tests as upstream runs it (nix/system-tests-vanilla).
        system-tests-default-fastapi = ddtrace.system-tests-vanilla.launchers.DEFAULT.fastapi;
        system-tests-vanilla-lock = ddtrace.system-tests-vanilla.lock;
        # The same scenario with the services declared in Nix (nix/system-tests).
        system-tests-nix-default-fastapi = ddtrace.scenarios.DEFAULT.fastapi;
        system-tests-trace-propagation-style-w3c-fastapi =
          ddtrace.scenarios.TRACE_PROPAGATION_STYLE_W3C.fastapi;
        inherit (ddtrace) system-tests-all;
      };
    };
}
