package com.datadoghq.trace.controller;

import static com.datadoghq.ApmTestClient.LOGGER;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.nio.file.Files;
import java.nio.file.Path;

@RestController
@RequestMapping(value = "/trace")
public class TraceController {
  /**
   * Crash tracking script path, as defined in run.sh script
   */
  private static final Path CRASH_TRACKING_SCRIPT = Path.of("/tmp/datadog/java/dd_crash_uploader.sh");

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
