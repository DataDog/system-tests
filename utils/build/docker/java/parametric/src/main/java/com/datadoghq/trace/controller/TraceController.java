package com.datadoghq.trace.controller;

import static com.datadoghq.ApmTestClient.LOGGER;

import com.datadoghq.trace.trace.dto.GetTraceConfigResult;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import datadog.trace.api.TracePropagationStyle;
import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;
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
    try
    {
        // Use reflection to get the static Config instance
        Class configClass = Class.forName("datadog.trace.api.Config");
        Method getConfigMethod = configClass.getMethod("get");

        Class instrumenterConfigClass = Class.forName("datadog.trace.api.InstrumenterConfig");
        Method getInstrumenterConfigMethod = instrumenterConfigClass.getMethod("get");

        Object configObject = getConfigMethod.invoke(null);
        Object instrumenterConfigObject = getInstrumenterConfigMethod.invoke(null);

        Method getServiceName = configClass.getMethod("getServiceName");
        Method getEnv = configClass.getMethod("getEnv");
        Method getVersion = configClass.getMethod("getVersion");
        Method getTraceSampleRate = configClass.getMethod("getTraceSampleRate");
        Method isTraceEnabled = configClass.getMethod("isTraceEnabled");
        Method isRuntimeMetricsEnabled = configClass.getMethod("isRuntimeMetricsEnabled");
        Method getGlobalTags = configClass.getMethod("getGlobalTags");
        Method getTracePropagationStylesToInject = configClass.getMethod("getTracePropagationStylesToInject");
        Method isDebugEnabled = configClass.getMethod("isDebugEnabled");
        Method getLogLevel = configClass.getMethod("getLogLevel");
        Method getAgentUrl = configClass.getMethod("getAgentUrl");
        Method getTraceRateLimit = configClass.getMethod("getTraceRateLimit");
        Method getJmxFetchStatsdPort = configClass.getMethod("getJmxFetchStatsdPort");
        Method getJmxFetchStatsdHost = configClass.getMethod("getJmxFetchStatsdHost");

        Method isTraceOtelEnabled = instrumenterConfigClass.getMethod("isTraceOtelEnabled");

        Map<String, String> configMap = new HashMap<>();
        configMap.put("dd_service", getServiceName.invoke(configObject).toString());
        configMap.put("dd_env", getEnv.invoke(configObject).toString());
        configMap.put("dd_version", getVersion.invoke(configObject).toString());
        configMap.put("dd_log_level", Optional.ofNullable(getLogLevel.invoke(configObject)).map(Object::toString).orElse(null));
        configMap.put("dd_trace_enabled", isTraceEnabled.invoke(configObject).toString());
        configMap.put("dd_runtime_metrics_enabled", isRuntimeMetricsEnabled.invoke(configObject).toString());
        configMap.put("dd_trace_debug", isDebugEnabled.invoke(configObject).toString());
        configMap.put("dd_trace_otel_enabled", isTraceOtelEnabled.invoke(instrumenterConfigObject).toString());
        configMap.put("dd_trace_agent_url", getAgentUrl.invoke(configObject).toString());
        // configMap.put("dd_trace_sample_ignore_parent", Config.get());

        Object dogstatsdHost = getJmxFetchStatsdHost.invoke(configObject);
        if (dogstatsdHost != null){
          configMap.put("dd_dogstatsd_host", getJmxFetchStatsdHost.invoke(configObject).toString());
        }

        Object sampleRate = getTraceSampleRate.invoke(configObject);
        if (sampleRate instanceof Double) {
            configMap.put("dd_trace_sample_rate", String.valueOf((Double)sampleRate));
        }

        Object rateLimit = getTraceRateLimit.invoke(configObject);
        if (rateLimit instanceof Integer) {
          configMap.put("dd_trace_rate_limit", Integer.toString((int)rateLimit));
        }

        Object statsPort = getJmxFetchStatsdPort.invoke(configObject);
        if (statsPort instanceof Integer) {
          configMap.put("dd_dogstatsd_port", Integer.toString((int)statsPort));
        }

        Object globalTags = getGlobalTags.invoke(configObject);
        if (globalTags != null) {
            String result = ((Map<String, String>)globalTags).entrySet()
                .stream()
                .map(entry -> entry.getKey() + ":" + entry.getValue())
                .collect(Collectors.joining(","));

            configMap.put("dd_tags", result);
        }

        Object propagationStyles = getTracePropagationStylesToInject.invoke(configObject);
        if (propagationStyles != null) {
            String result = ((Set<TracePropagationStyle>)propagationStyles)
                .stream()
                .map(style -> style.toString())
                .collect(Collectors.joining(","));

            configMap.put("dd_trace_propagation_style", result);
        }

        configMap.values().removeIf(Objects::isNull);
        return new GetTraceConfigResult(configMap);
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
