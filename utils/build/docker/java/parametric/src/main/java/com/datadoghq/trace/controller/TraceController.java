package com.datadoghq.trace.controller;

import static com.datadoghq.ApmTestClient.LOGGER;
import static java.util.Map.entry;

import com.datadoghq.trace.dto.GetTraceConfigResult;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.nio.file.Files;
import java.nio.file.Path;

@RestController
@RequestMapping(value = "/trace")
public class TraceController {
  /**
   * Crash tracking script path, as defined in run.sh script
   */
  private static final Path CRASH_TRACKING_SCRIPT = Path.of("/tmp/datadog/java/dd_crash_uploader.sh");

  @GetMapping("config")
  public GetTraceConfigResult config() {
    LOGGER.info("Getting tracer config");
    try {
      ConfigHelper helper = new ConfigHelper();
      var configMapping = Map.ofEntries(
          entry("dd_service", "getServiceName"),
          entry("dd_env", "getEnv"),
          entry("dd_version", "getVersion"),
          entry("dd_log_level", "getLogLevel"),
          entry("dd_trace_enabled", "isTraceEnabled"),
          entry("dd_runtime_metrics_enabled", "isRuntimeMetricsEnabled"),
          entry("dd_trace_debug", "isDebugEnabled"),
          entry("dd_trace_agent_url", "getAgentUrl"),
          entry("dd_dogstatsd_host", "getJmxFetchStatsdHost"),
          entry("dd_dogstatsd_port", "getJmxFetchStatsdPort"),
          entry("dd_trace_sample_rate", "getTraceSampleRate"),
          entry("dd_trace_rate_limit", "getTraceRateLimit"),
          entry("dd_logs_injection", "isLogsInjectionEnabled"),
          entry("dd_profiling_enabled", "isProfilingEnabled"),
          entry("dd_data_streams_enabled", "isDataStreamsEnabled")
      );
      Map<String, String> config = new HashMap<>();
      configMapping.forEach(
          (key, accessor) -> config.put(key, helper.getConfigValue(accessor))
      );
      config.put("dd_trace_propagation_style", helper.getConfigCollectionValues("getTracePropagationStylesToInject", ","));
      config.put("dd_tags", helper.getConfigMapValues("getGlobalTags", ",", ":"));
      config.put("dd_trace_otel_enabled", helper.getInstrumenterConfigValue("isTraceOtelEnabled"));

      config.values().removeIf(Objects::isNull);
      return new GetTraceConfigResult(config);
    } catch (Throwable t) {
      LOGGER.error("Uncaught throwable", t);
      return GetTraceConfigResult.error();
    }
  }

  @GetMapping("crash")
  public void crash() {
    LOGGER.info("Crashing client app");
    try {
      waitForCrashTrackingScriptSetup();
      ProcessHandle current = ProcessHandle.current();
      Runtime.getRuntime().exec("kill -11 " + current.pid());
    } catch (Exception e) {
      LOGGER.warn("Failed to crash client app", e);
    }
  }

  /**
   * Wait for crash tracking related script to be initialized.
   * Its installation is deferred at startup and can be trigger earlier setting {@code dd.jmxfetch.start-delay} to zero.
   *
   * @throws InterruptedException If it fails to wait for the script initialization.
   */
  private void waitForCrashTrackingScriptSetup() throws InterruptedException {
    boolean setup = false;
    int maxRetries = 30;
    while (!setup && maxRetries-- > 0) {
      setup = Files.exists(CRASH_TRACKING_SCRIPT);
      Thread.sleep(1_000);
    }
    if (!setup) {
      throw new IllegalStateException("Crash tracking script not found");
    }
  }
}
