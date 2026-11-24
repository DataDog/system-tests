# system-tests' TRACE_PROPAGATION_STYLE_W3C scenario (utils/_context/_scenarios/tracing_config.py):
# the end-to-end services, the weblog propagating W3C trace context only.
{ ... }:
{
  imports = [ ../end-to-end.nix ];

  scenario = "TRACE_PROPAGATION_STYLE_W3C";

  services.weblog.environment = {
    DD_TRACE_PROPAGATION_STYLE_INJECT = "tracecontext";
    DD_TRACE_PROPAGATION_STYLE_EXTRACT = "tracecontext";
  };
}
