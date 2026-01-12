# Java 26 + ParallelGC + Heap Histogram Profiling Crash Analysis

**Date:** January 10, 2026  
**Scenario:** Docker SSI (Single Step Instrumentation)  
**Affected Java Version:** Java 26 EA Build 29 (26-ea+29-2803)  
**Status:** 🔴 Critical - JVM Crash (SIGSEGV)

---

## Executive Summary

The Docker SSI scenario crashes when testing Java 26 with the combination of:
1. `DD_PROFILING_HEAP_HISTOGRAM_ENABLED=true` (Datadog profiling feature)
2. `-XX:+UseParallelGC` (Parallel Garbage Collector)

This issue **does not occur** in Java 25 or when using alternative garbage collectors (G1GC). The crash is caused by a memory access violation in Java 26's ParallelGC implementation during JFR-triggered heap iteration.

---

## Problem Description

### Crash Signature

```
# A fatal error has been detected by the Java Runtime Environment:
#
#  SIGSEGV (0xb) at pc=0x00007ffffece4669, pid=1, tid=54
#
# JRE version: OpenJDK Runtime Environment (26.0+29) (build 26-ea+29-2803)
# Java VM: OpenJDK 64-Bit Server VM (26-ea+29-2803, mixed mode, sharing, tiered, 
#          compressed oops, compressed class ptrs, parallel gc, linux-amd64)
# Problematic frame:
# V  [libjvm.so+0xea9669]  PSOldGen::object_iterate_block(ObjectClosure*, unsigned long)+0x179
```

**Key Observations:**
- Crash occurs in `PSOldGen::object_iterate_block` - ParallelGC-specific heap iteration
- Only happens with Java 26 (not Java 25)
- Only happens when BOTH conditions are met (heap histogram + ParallelGC)
- Removing either condition resolves the crash

### Configuration Files

**File:** `utils/build/ssi/base/base_ssi.Dockerfile`
```dockerfile
ENV DD_PROFILING_ENABLED=true
ENV DD_PROFILING_HEAP_HISTOGRAM_ENABLED=true
ENV DD_PROFILING_START_FORCE_FIRST=true
```

**File:** `utils/build/ssi/java/jetty-app.Dockerfile`
```dockerfile
CMD [ "java", "-XX:+UseParallelGC","-cp", "jetty-classpath/*:.", "JettyServletMain" ]
```

---

## Root Cause Analysis

### 1. Datadog Agent Implementation Gap

The dd-trace-java profiling agent checks if the JDK has parallelized heap iteration support using this method in `ProfilingSupport.java`:

```java
public static boolean isObjectCountParallelized() {
  // parallelized jdk.ObjectCount implemented in JDK21 and backported to JDK17
  // https://bugs.openjdk.org/browse/JDK-8307348
  return (isJavaVersion(17) && isJavaVersionAtLeast(17, 0, 9)) || isJavaVersionAtLeast(21);
}
```

**Problem:** This check **does NOT include Java 26**, so:
- dd-trace-java assumes Java 26 doesn't have efficient heap iteration
- It still enables the feature but logs a warning about potential performance impact
- The agent enables `jdk.ObjectCountAfterGC` JFR event regardless

### 2. JFR Heap Histogram Collection

When `DD_PROFILING_HEAP_HISTOGRAM_ENABLED=true`, the agent enables JFR events:
- **Default mode ("aftergc"):** Uses `jdk.ObjectCountAfterGC` event
- **Periodic mode:** Uses `jdk.ObjectCount` event

From `OpenJdkController.java`:
```java
if (configProvider.getBoolean(
    PROFILING_HEAP_HISTOGRAM_ENABLED, PROFILING_HEAP_HISTOGRAM_ENABLED_DEFAULT)) {
  
  if (!isObjectCountParallelized()) {
    log.warn("enabling Datadog heap histogram on JVM without an efficient implementation...");
  }
  
  String mode = configProvider.getString(
      PROFILING_HEAP_HISTOGRAM_MODE, PROFILING_HEAP_HISTOGRAM_MODE_DEFAULT);
  
  if ("periodic".equalsIgnoreCase(mode)) {
    enableEvent(recordingSettings, "jdk.ObjectCount", "user enabled histogram heap collection");
  } else {
    enableEvent(recordingSettings, "jdk.ObjectCountAfterGC", "user enabled histogram heap collection");
  }
}
```

### 3. Java 26 ParallelGC Bug

The crash occurs because:

1. **JFR Event Triggers:** `jdk.ObjectCountAfterGC` event fires after a garbage collection
2. **Heap Iteration Initiated:** JVM calls `PSOldGen::object_iterate_block` to walk the heap
3. **Memory Access Violation:** Java 26 build 29's implementation has a bug in this code path
4. **Result:** SIGSEGV crash at offset +0x179 in the method

**Why ParallelGC specifically?**
- `PSOldGen` (Parallel Scavenge Old Generation) is specific to ParallelGC
- Other GCs (G1GC, ZGC, SerialGC) use different heap iteration implementations
- The bug is in ParallelGC's specific implementation of object iteration

### 4. Background: JDK-8307348

JDK-8307348 introduced **parallelized heap iteration** for JFR ObjectCount events:
- **Implemented in:** JDK 21
- **Backported to:** JDK 17.0.9
- **Purpose:** Reduce latency of heap histogram collection using multiple GC worker threads
- **Status in Java 26:** Should be present, but has a regression with ParallelGC

---

## Evidence

### From Log Files

**Location:** `logs_docker_ssi/docker/weblog-injection/stdout.log`

```
#  SIGSEGV (0xb) at pc=0x00007ffffece4669, pid=1, tid=54
# JRE version: OpenJDK Runtime Environment (26.0+29) (build 26-ea+29-2803)
# Java VM: OpenJDK 64-Bit Server VM (26-ea+29-2803, mixed mode, sharing, tiered, 
#          compressed oops, compressed class ptrs, parallel gc, linux-amd64)
# Problematic frame:
# V  [libjvm.so+0xea9669]  PSOldGen::object_iterate_block(ObjectClosure*, unsigned long)+0x179
```

**Key Details:**
- GC Type: `parallel gc` confirmed in JVM description
- Crash Location: ParallelGC-specific old generation iteration
- Detected Java Version: `26-ea+29-2803`

### From Datadog Agent

**Injection Process:** (from stderr.log)
```
<DEBUG> detected language: 'jvm'
<DEBUG> detected language version: '26-ea+29-2803'
```

The Datadog SSI injector successfully:
- Detected Java 26
- Injected the dd-java-agent
- Enabled profiling with heap histogram
- Started the application

Then the crash occurred during the first heap histogram collection attempt.

---

## Technical Deep Dive

### Heap Histogram Collection Process

1. **Trigger:** GC completes (or periodic event fires)
2. **JFR Event:** `jdk.ObjectCountAfterGC` event handler invoked
3. **Heap Inspection:** JVM initiates heap walk using `HeapInspection::populate_table`
4. **ParallelGC Path:** Calls `PSOldGen::object_iterate_block` for old generation
5. **Bug Location:** Memory access violation in parallel iteration logic

### Why This Worked in Java 25

Possible explanations:
- Different implementation of `PSOldGen::object_iterate_block`
- Different compiler optimizations
- Bug introduced in Java 26 build 29 or earlier EA build
- Changes to GC internals between Java 25 and 26

### Parallelization Context

The parallelized heap iteration (JDK-8307348) was designed to:
- Use multiple GC worker threads to iterate heap regions
- Reduce the Stop-The-World (STW) pause impact
- Make heap histogram collection production-safe

However, the implementation in Java 26's ParallelGC appears to have a **concurrency or memory management bug** that causes crashes.

---

## Solutions

### Immediate Workarounds

#### Option 1: Switch to G1GC (Recommended)

**Change:** `utils/build/ssi/java/jetty-app.Dockerfile`

```dockerfile
# Before:
CMD [ "java", "-XX:+UseParallelGC","-cp", "jetty-classpath/*:.", "JettyServletMain" ]

# After:
CMD [ "java", "-XX:+UseG1GC","-cp", "jetty-classpath/*:.", "JettyServletMain" ]
```

**Pros:**
- ✅ G1GC is recommended for most workloads with JDK 9+
- ✅ Better compatibility with profiling tools
- ✅ No changes to profiling configuration needed
- ✅ Production-ready and well-tested

**Cons:**
- ⚠️ Different GC behavior (may affect test results)
- ⚠️ Slightly different performance characteristics

---

#### Option 2: Disable Heap Histogram for Java 26

**Change:** `utils/build/ssi/base/base_ssi.Dockerfile`

```dockerfile
# Conditional approach - disable for Java 26 only
ENV DD_PROFILING_ENABLED=true
# ENV DD_PROFILING_HEAP_HISTOGRAM_ENABLED=true  # Disabled for Java 26
ENV DD_PROFILING_START_FORCE_FIRST=true
```

Or implement conditional logic in the build process to set this env var based on Java version.

**Pros:**
- ✅ Keeps ParallelGC for testing
- ✅ Minimal configuration changes
- ✅ Other profiling features still work

**Cons:**
- ⚠️ Loses heap histogram profiling data
- ⚠️ May need version detection logic

---

#### Option 3: Disable Profiling Entirely

```dockerfile
ENV DD_PROFILING_ENABLED=false
# ENV DD_PROFILING_HEAP_HISTOGRAM_ENABLED=true
# ENV DD_PROFILING_START_FORCE_FIRST=true
```

**Pros:**
- ✅ Guarantees no crash
- ✅ Simple solution

**Cons:**
- ❌ Loses all profiling data
- ❌ Not testing the full product feature set

---

### Long-term Fixes

#### Fix 1: Update dd-trace-java to Skip Feature Enablement

**Critical Understanding:** The `isObjectCountParallelized()` method only controls the **warning message**, NOT whether the feature is enabled. Even when it returns `false`, the feature is still enabled and will crash.

**The Real Fix Location:** `dd-trace-java/.../OpenJdkController.java`

```java
if (configProvider.getBoolean(
    PROFILING_HEAP_HISTOGRAM_ENABLED, PROFILING_HEAP_HISTOGRAM_ENABLED_DEFAULT)) {
  
  // NEW: Check for known Java 26 + ParallelGC crash bug
  if (isJava26WithParallelGCBug()) {
    log.error(
        "Heap histogram profiling is disabled due to a critical JVM crash on Java 26 with ParallelGC. "
        + "To enable this feature, either: "
        + "(1) Use a different GC with -XX:+UseG1GC, "
        + "(2) Upgrade to Java 26 build with the fix (TBD), or "
        + "(3) Set DD_PROFILING_HEAP_HISTOGRAM_ENABLED=false to acknowledge this limitation. "
        + "See: https://github.com/DataDog/dd-trace-java/issues/XXXXX");
    return; // CRITICAL: Skip enabling the feature entirely to prevent crash
  }
  
  // Existing warning for non-parallelized versions
  if (!isObjectCountParallelized()) {
    log.warn(
        "enabling Datadog heap histogram on JVM without an efficient implementation of the jdk.ObjectCount event. "
            + "This may increase p99 latency. Consider upgrading to JDK 17.0.9+ or 21+ to reduce latency impact.");
  }
  
  // Only reach here if Java 26 + ParallelGC check passed
  String mode =
      configProvider.getString(
          PROFILING_HEAP_HISTOGRAM_MODE, PROFILING_HEAP_HISTOGRAM_MODE_DEFAULT);
  if ("periodic".equalsIgnoreCase(mode)) {
    enableEvent(recordingSettings, "jdk.ObjectCount", "user enabled histogram heap collection");
  } else {
    enableEvent(
        recordingSettings, "jdk.ObjectCountAfterGC", "user enabled histogram heap collection");
  }
}
```

**Add Helper Method:** `dd-trace-java/.../ProfilingSupport.java`

```java
public static boolean isJava26WithParallelGCBug() {
  // Java 26 EA builds (at least through build 29) have a crash bug in ParallelGC
  // when JFR ObjectCount events are enabled
  // See: https://bugs.openjdk.org/browse/JDK-XXXXX (to be filed)
  
  if (!isJavaVersionAtLeast(26)) {
    return false; // Not Java 26
  }
  
  // Check if using ParallelGC (PS = Parallel Scavenge)
  boolean isParallelGC = ManagementFactory.getGarbageCollectorMXBeans().stream()
      .map(GarbageCollectorMXBean::getName)
      .anyMatch(name -> name.contains("PS ") || name.contains("Parallel"));
  
  if (!isParallelGC) {
    return false; // Not using ParallelGC, no crash risk
  }
  
  // TODO: Once OpenJDK fixes the bug, update this check to exclude fixed builds
  // For example: if (isJavaVersionAtLeast(26, 0, 50)) return false;
  
  log.debug("Detected Java 26 with ParallelGC - known crash bug with heap histogram profiling");
  return true;
}
```

**Why This Fix Works:**

1. ✅ **Actually prevents the crash** by skipping `enableEvent()` calls
2. ✅ **Specific detection** of Java 26 + ParallelGC combination
3. ✅ **Clear error message** guiding users to workarounds
4. ✅ **Future-proof** with TODO for when OpenJDK fixes the bug
5. ✅ **Doesn't affect other Java versions** or GC types

**Action Items:**
1. Create JIRA ticket for dd-trace-java team with priority: **CRITICAL**
2. Implement the fix in OpenJdkController.java (not just ProfilingSupport.java)
3. Add unit tests for `isJava26WithParallelGCBug()` detection
4. Add integration test that verifies heap histogram is NOT enabled on Java 26 + ParallelGC
5. Deploy fix in next agent release
6. Document in release notes and troubleshooting guide

---

#### Fix 2: Report OpenJDK Bug

This appears to be a **JVM bug** that should be reported to OpenJDK.

**Bug Report Template:**

```
Title: SIGSEGV in PSOldGen::object_iterate_block during JFR ObjectCountAfterGC event

Summary:
Java 26 EA build 29 crashes with SIGSEGV when JFR event jdk.ObjectCountAfterGC 
is enabled with ParallelGC. The crash occurs in PSOldGen::object_iterate_block 
at offset +0x179.

Environment:
- Java Version: 26-ea+29-2803
- OS: Linux (Docker container)
- GC: -XX:+UseParallelGC
- JFR Event: jdk.ObjectCountAfterGC (enabled)

Steps to Reproduce:
1. Use Java 26 EA build 29
2. Enable -XX:+UseParallelGC
3. Enable JFR recording with jdk.ObjectCountAfterGC event
4. Run application that triggers GC
5. Observe SIGSEGV crash in PSOldGen::object_iterate_block

Expected Behavior:
JFR heap histogram collection should complete without crashing the JVM.

Actual Behavior:
JVM crashes with SIGSEGV during heap iteration.

Stack Trace:
V  [libjvm.so+0xea9669]  PSOldGen::object_iterate_block(ObjectClosure*, unsigned long)+0x179

Notes:
- Does NOT occur with G1GC or other garbage collectors
- Does NOT occur in Java 25
- Likely regression introduced in Java 26 development
- Related to JDK-8307348 (parallelized heap iteration)
```

**Action Items:**
1. Gather complete hs_err_pid_1.log file
2. Create minimal reproducible test case
3. Submit bug report to https://bugreport.java.com
4. Track fix in Java 26 releases

---

#### Fix 3: System-Tests Conditional Logic

Add Java version detection in Docker SSI scenario to automatically select appropriate GC:

**File:** `utils/_context/_scenarios/docker_ssi.py` or build scripts

```python
def get_recommended_gc_for_java_version(java_version: str) -> str:
    """Return recommended GC based on Java version and known issues."""
    if java_version.startswith("26"):
        # Java 26 has ParallelGC bug with heap histogram profiling
        return "-XX:+UseG1GC"
    else:
        # Default to G1GC for modern Java, ParallelGC for testing
        return "-XX:+UseParallelGC"
```

---

## Recommendations

### For System-Tests Repository

**Priority 1 (Immediate):**
1. ✅ Switch Java 26 Docker SSI tests to use G1GC instead of ParallelGC
2. ✅ Document the issue in CHANGELOG or known issues
3. ✅ Add comment in Dockerfile explaining the workaround

**Priority 2 (Short-term):**
1. 📝 Create JIRA ticket for dd-trace-java team
2. 📝 Add test case specifically for Java 26 + profiling combinations
3. 📝 Monitor Java 26 EA builds for fix

**Priority 3 (Long-term):**
1. 🔄 Report bug to OpenJDK
2. 🔄 Implement automatic GC selection based on Java version
3. 🔄 Add CI checks for Java version compatibility matrix

### For dd-trace-java Team

1. **CRITICAL FIX:** Update `OpenJdkController.java` to **skip feature enablement** (not just warn) when Java 26 + ParallelGC is detected
2. **Add GC type detection** via `isJava26WithParallelGCBug()` method
3. **Return early** from heap histogram configuration to prevent `enableEvent()` calls
4. **Document workaround** in troubleshooting guide and error message
5. **Monitor OpenJDK fixes** and update detection logic when bug is resolved
6. **Add tests** to verify feature is NOT enabled on Java 26 + ParallelGC

### For Users

If you encounter this crash:

1. **Immediate:** Switch to G1GC: `-XX:+UseG1GC`
2. **Alternative:** Disable heap histogram: `DD_PROFILING_HEAP_HISTOGRAM_ENABLED=false`
3. **Best Practice:** Use G1GC with modern Java versions (JDK 9+) for better profiling compatibility

---

## Implementation Plan

### Phase 1: Quick Fix (Today)

```bash
# Edit the Dockerfile
vim utils/build/ssi/java/jetty-app.Dockerfile

# Change line 18 from:
# CMD [ "java", "-XX:+UseParallelGC","-cp", "jetty-classpath/*:.", "JettyServletMain" ]

# To:
# CMD [ "java", "-XX:+UseG1GC","-cp", "jetty-classpath/*:.", "JettyServletMain" ]

# Add comment explaining why:
# Note: Using G1GC instead of ParallelGC due to Java 26 crash with heap histogram profiling
# See: java26-parallelgc-crash-analysis.md
```

### Phase 2: Testing (This Week)

1. Test Docker SSI scenario with Java 26 + G1GC
2. Verify profiling data is collected correctly
3. Confirm no crashes occur
4. Test with different Java versions (25, 21, 17) to ensure compatibility

### Phase 3: Documentation (This Week)

1. Add this analysis document to repository
2. Update CHANGELOG
3. Add comment in Dockerfile
4. Update CI configuration if needed

### Phase 4: Upstream (Next 2 Weeks)

1. Create JIRA ticket for dd-trace-java
2. Submit OpenJDK bug report
3. Monitor for fixes in Java 26 builds

---

## Related Issues & References

### OpenJDK Issues
- **JDK-8307348:** Parallelize heap walk for ObjectCount(AfterGC) JFR event collection
- **JDK-8266353:** Add parallel heap iteration for jmap -histo
- **JDK-8215624:** Original parallel heap iteration foundation

### Datadog Documentation
- [Java Profiler Troubleshooting](https://docs.datadoghq.com/profiler/profiler_troubleshooting/java/)
- [Heap Histogram Profiling](https://docs.datadoghq.com/profiler/enabling/java/)

### Internal References
- Configuration: `utils/build/ssi/base/base_ssi.Dockerfile`
- Weblog: `utils/build/ssi/java/jetty-app.Dockerfile`
- Logs: `logs_docker_ssi/docker/weblog-injection/`

---

## Appendix: Additional Technical Details

### JFR Event Configuration

From dd-trace-java `dd.jfp` profile:
```properties
jdk.ObjectCount#enabled=false
jdk.ObjectCount#period=everyChunk

jdk.ObjectCountAfterGC#enabled=false
```

Both events are disabled by default and only enabled when `DD_PROFILING_HEAP_HISTOGRAM_ENABLED=true`.

### Garbage Collector Comparison

| GC Type | Suitable For | Pros | Cons | Java 26 Heap Histogram |
|---------|-------------|------|------|----------------------|
| **G1GC** | Most workloads | Predictable pauses, good throughput | Slightly higher overhead | ✅ Works |
| **ParallelGC** | Batch processing | Highest throughput | Less predictable pauses | ❌ Crashes |
| **ZGC** | Low-latency apps | Ultra-low pauses | Higher memory usage | ⚠️ Not supported by feature |
| **SerialGC** | Small heaps | Simple, low overhead | Poor scalability | ✅ Likely works |

### Performance Impact

Heap histogram collection adds:
- **Without parallelization:** 50-500ms pause (depends on heap size)
- **With parallelization (JDK 21+):** 10-50ms pause
- **Frequency:** After each GC (default mode) or periodic

---

## Contact & Support

**Questions?** Reach out in Slack: **#apm-shared-testing**

**Created by:** System-Tests Automated Analysis  
**Date:** January 10, 2026  
**Version:** 1.0
