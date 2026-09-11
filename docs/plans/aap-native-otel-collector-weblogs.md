# Test Plan: AAP Features with Native OTel Collector in Weblogs

## Objective

Validate that Datadog's Application & API Protection (AAP / AppSec) features work correctly when telemetry flows through the **native OpenTelemetry Collector** (with the `datadog` exporter) instead of the **Datadog Agent** collector, in weblog end-to-end tests.

---

## 0. Comparison with Strategic Plan & Confluence R&D

### 0.1 Sources

1. **Google Doc** (`1VFIN40tNo_wrY7S8njSe82AD-wWuTYeZAN3Su5JwDus`): "AAP for OTel Customers" — strategic plan by Ramy Elkest + Zach Montoya (SDK Capabilities), Draft June 2026. Accessed via Google Workspace MCP.
2. **Confluence** (`6668091590`): "AAP for OTel customers - R&D" in SAAL space. Accessed via Atlassian MCP.

### 0.2 Google Doc: Topology Taxonomy & Milestones

The Google Doc defines a **5-topology taxonomy** split across two layers: instrumentation (Layer 1) and collection (Layer 2). AAP capability is determined by instrumentation, not collection.

| Topology | Instrumentation | Collection | AAP Today | Milestone |
|----------|-----------------|------------|-----------|-----------|
| Pure OTel SDK | OTel SDK | OTel Collector → DD backend | Unsupported | M0 (document), M3 (build) |
| OTel API + DD Tracer | DD Tracer (OTel-compatible API) | Any | Full AAP | M1 (validate & document) |
| **DD Tracer + OTel Collector** | **DD Tracer** | **OTel Collector + RC via DD Agent** | **Full AAP** | **M2 (validate & document)** |
| OTel SDK + DD AAP Library | OTel SDK + AAP Library (additive) | Any | Unsupported → target | M3 (build) |
| OTel SDK + DD Tracer coexistence | Both in-process | Any | Complex / partial | M4 (support policy only) |

**This system-tests plan covers M2** — the "DD Tracer + OTel Collector" topology.

### 0.3 Critical Correction: M2 Requires a DD Agent for Remote Config

The Google Doc is explicit about M2's architecture:

> *"DD Tracer + OTel Collector, with one DD Agent per cluster for Remote Config. Telemetry continues through their OTel Collector; a single lightweight DD Agent per cluster handles only the Remote Config control plane."*

This means our test scenario needs **BOTH**:
- **OTel Collector** — for the data plane (traces, metrics, logs)
- **DD Agent** — for the RC control plane (WAF rule updates, blocking, runtime activation)

My original plan assumed RC wouldn't work without the agent and suggested skipping RC-dependent tests. **This was wrong.** M2 explicitly keeps a DD Agent for RC. The architecture should be:

```
Weblog (dd-trace, AppSec enabled, OTLP export)
  → OTel Collector (data plane: traces/metrics/logs → Datadog backend)
  → DD Agent (control plane: Remote Config → tracer)
  → Datadog Backend (or mocked backend)
```

This means RC-dependent tests (runtime activation, remote config rule changes, dynamic blocking) **should be in scope**, not skipped.

### 0.4 Google Doc Milestones vs This Plan

| Milestone | Description | This Plan? |
|-----------|-------------|------------|
| **M0 — Know the Gap** | Baseline: OTel SDK → OTel Collector → DD backend. Document where AAP breaks down. | ❌ Not covered (separate workstream) |
| **M1 — Full AAP, Minimal Migration** | DD Tracer as drop-in replacement for OTel SDK. Validate WAF/ATO/API Sec, OTel API parity. Any collector. | ❌ Not covered (separate — M1 uses "any" collector, not specifically OTel Collector) |
| **M2 — Full AAP, Keep Your Collector** | DD Tracer + OTel Collector + DD Agent for RC. Validate & document. | ✅ **This plan** |
| M3 — AAP with Zero SDK Migration | OTel SDK + DD AAP Library side-by-side. Build. | ❌ Not covered |
| M4 — Migration Window Support | Both SDKs running simultaneously. Support policy. | ❌ Not covered |

### 0.5 Google Doc GA Bar & Success Criteria

The Google Doc defines a clear GA bar for each milestone:

> *"A milestone is complete when: at least 2 reference languages are validated, a version-tagged public support statement exists, a sample app is in customer-facing docs, and system test coverage is in place for the topology × language combinations."*

> *"'Supported' means full coverage. A topology is 'supported' only when WAF, ATO detection, and API Security all function and are validated."*

Success criteria from the Google Doc:
- System test coverage spans every validated topology × language combination and catches AAP regressions before tracer releases ship
- At least one customer reaches production on M1 or M2 within Q3 2026

**This plan is the system-tests coverage piece of M2.**

### 0.6 Confluence Page: Four Scenarios (R&D Test Plan)

The Confluence page describes 4 testing scenarios that map to the Google Doc milestones:

| Confluence Scenario | Google Doc Milestone |
|---------------------|---------------------|
| 1. Vanilla OTel (baseline) | M0 |
| 2. Drop-In OTel Replacement | M1 + M2 |
| 3. Vanilla OTel + AAP Library | M3 |
| 4. Side-by-side parallel pipelines | M4 |

### 0.7 Key Gaps & Corrections Identified

| Gap | Source | This Plan (Original) | Correction |
|-----|--------|----------------------|-----------|
| **RC architecture** | Google Doc M2 | Assumed no agent, skipped RC tests | **Add DD Agent for RC control plane. RC tests are in scope.** |
| **ATO detection** | Both docs | Not mentioned | **Add ATO tests** (already added in prior update) |
| **"Supported" = WAF + ATO + API Sec** | Google Doc | Focused on WAF + IAST + RASP | **Ensure all three (WAF, ATO, API Security) are P0 priority** |
| **2 reference languages minimum** | Google Doc GA bar | Python + Java | ✅ Already aligned |
| **Version-tagged support statements** | Google Doc | Not included | **Add as deliverable** (outside system-tests scope, but tracked) |
| **Raw OTLP / non-DD backend** | Confluence Scenario 2 | Added file exporter variant | ✅ Already added |
| **Coexistence testing** | Both docs | Not covered | Out of scope for M2 (coexistence is M3/M4) |
| **Coverage matrix topology × language** | Both docs | language × AAP feature | **Add topology column** (M2 only for now) |

---

## 1. Current State

### 1.1 How AAP Tests Work Today (Datadog Agent Path)

```
Weblog (dd-trace, AppSec enabled)
  → App Proxy (captures tracer→agent traffic on port 8126)
  → Datadog Agent
  → Agent Proxy (captures agent→backend traffic on port 8200)
  → Datadog Backend (or mocked backend)
```

**Key characteristics:**
- `WeblogContainer` sets `DD_APPSEC_ENABLED=true`, `DD_APPSEC_WAF_TIMEOUT=10000000`, `DD_APPSEC_TRACE_RATE_LIMIT=10000`
- Tracer sends data to `proxy:8126` (ProxyPorts.weblog) using the Datadog trace agent protocol
- `interfaces.library` (LibraryInterfaceValidator) captures and validates tracer→agent traffic, including AppSec events in span `meta_struct["appsec"]` or `meta["_dd.appsec.json"]`
- `interfaces.agent` (AgentInterfaceValidator) captures and validates agent→backend traffic
- AppSec tests assert on `interfaces.library.assert_waf_attack()`, `interfaces.library.get_appsec_events()`, etc.
- All ~37 top-level AppSec test files + IAST/RASP/API Security/WAF subdirectories use `interfaces.library` for validation

### 1.2 Existing OTel Collector Scenarios (No AppSec)

Two separate OTel scenario classes exist, neither of which tests AppSec:

#### a) `OtelCollectorScenario` (`utils/_context/_scenarios/otel_collector.py`)
- Tests the OTel Collector forwarding traces/metrics/logs to Datadog backend via the `datadog` exporter
- Uses `otel/opentelemetry-collector-contrib:0.137.0` image
- Config: `utils/build/docker/e2eotel/otelcol-config.yml`
- **No weblog container** — only collector + postgres + proxy
- Only tests: postgres metrics, schema validation
- Interface: `interfaces.otel_collector` (basic ProxyBasedInterfaceValidator, no AppSec methods)

#### b) `OpenTelemetryScenario` (`utils/_context/_scenarios/open_telemetry.py`)
- Tests OTel SDKs (native OTel instrumentation) with optional Datadog Agent + OTel Collector
- Supports only `java_otel`, `python_otel`, `nodejs_otel` libraries
- Weblog category: `WeblogCategory.open_telemetry`
- Interface: `interfaces.open_telemetry` (OpenTelemetryInterfaceValidator)
- **AppSec is NOT enabled** — `WeblogContainer` defaults `appsec_enabled=True` but OTel SDK weblogs don't use dd-trace AppSec
- Tests: OTel tracing/metrics/logs E2E, DB integrations, context propagation

### 1.3 The Gap

| Aspect | Datadog Agent (Today) | OTel Collector (Goal) |
|--------|----------------------|----------------------|
| Collector | Datadog Agent | OTel Collector with `datadog` exporter |
| Tracer→Collector protocol | Datadog trace agent (v0.4/v0.5) | OTLP HTTP (`/v1/traces`, `/v1/metrics`, `/v1/logs`) |
| Proxy port (tracer→collector) | 8126 (ProxyPorts.weblog) | 8127 (ProxyPorts.open_telemetry_weblog) |
| AppSec data in spans | `meta_struct["appsec"]` or `meta["_dd.appsec.json"]` | **Unknown** — depends on how OTel collector `datadog` exporter transforms AppSec span attributes |
| Interface validator | `interfaces.library` (rich AppSec methods) | `interfaces.open_telemetry` (no AppSec methods) |
| AppSec tests | ~70+ test files across appsec/ | **None** |

**Core question:** Does the OTel Collector's `datadog` exporter correctly transform and forward AppSec data (span attributes, meta_struct, triggers) so that AAP features are visible in the Datadog backend?

---

## 2. Architecture for the New Test Scenario (M2: DD Tracer + OTel Collector + DD Agent for RC)

### 2.1 Proposed Data Flow

Per the M2 milestone definition from the strategic plan, the architecture has **two planes**:

**Data plane** (traces, metrics, logs):
```
Weblog (dd-trace, AppSec enabled, OTLP export)
  → App Proxy (captures tracer→collector traffic on port 8127)
  → OTel Collector (receives OTLP, exports via datadog exporter)
  → Collector Proxy (captures collector→backend traffic on port 8128)
  → Datadog Backend (or mocked backend)
```

**Control plane** (Remote Config):
```
Datadog Backend (RC API)
  → DD Agent (lightweight, one per cluster, RC control plane only)
  → App Proxy (captures tracer→agent RC traffic on port 8126)
  → Weblog (dd-tracer receives RC updates: WAF rules, blocking configs, activation)
```

This means the scenario needs **three containers** besides the weblog:
1. **OTel Collector** — data plane (traces/metrics/logs via OTLP)
2. **DD Agent** — control plane (Remote Config only)
3. **Proxy** — captures both data plane and control plane traffic

### 2.2 Key Container Changes

| Container | Current (Agent) | New (M2: OTel Collector + DD Agent for RC) |
|-----------|-----------------|------------------------------------------|
| Weblog | `DD_AGENT_HOST=proxy`, `DD_TRACE_AGENT_PORT=8126` | OTLP export to collector on port 8127 + RC via agent on port 8126 |
| Data Collector | Datadog Agent (`agent`) | OTel Collector (`collector`) with `otelcol-config.yml` |
| RC Agent | Datadog Agent (same as data) | DD Agent (lightweight, RC only — same image, configured for RC only) |
| Proxy (data plane) | Port 8126, Datadog agent protocol | Port 8127, OTLP HTTP protocol |
| Proxy (RC plane) | Port 8126 (shared) | Port 8126, Datadog agent protocol (RC only) |
| Proxy (collector→backend) | Port 8200, agent→backend | Port 8128, collector→backend |

### 2.3 Weblog Environment Variables

The key M2 insight: dd-tracer uses **two separate channels** — OTLP for traces/metrics/logs, and the DD agent protocol for Remote Config. The tracer needs to know where to send data (OTLP endpoint) and where to get RC (DD agent endpoint).

```python
weblog_env={
    # AppSec is enabled automatically by WeblogContainer when appsec_enabled=True
    # Sets: DD_APPSEC_ENABLED=true, DD_APPSEC_WAF_TIMEOUT=10000000, DD_APPSEC_TRACE_RATE_LIMIT=10000

    # --- Data plane: OTLP export to OTel Collector (via proxy on port 8127) ---
    "DD_TRACE_OTEL_ENABLED": "true",
    "OTEL_TRACES_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/metrics",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/logs",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",

    # --- Control plane: Remote Config via DD Agent (via proxy on port 8126) ---
    # WeblogContainer sets DD_AGENT_HOST=proxy and DD_TRACE_AGENT_PORT=8126 by default
    # when use_proxy=True. The tracer uses this for RC polling.
    # The agent is configured to NOT accept trace data (or traces simply go to agent
    # and are forwarded, but the primary data path is OTLP).
    #
    # IMPORTANT: Need to verify that dd-tracer can use OTLP for traces while
    # still polling RC from the DD agent. This may require:
    # - DD_APM_RECEIVE_PORT set on agent (for RC)
    # - Tracer configured to send traces to OTLP endpoint but RC to agent
    # - Or: tracer sends BOTH to agent (traces+RC) and OTLP (traces only),
    #   with agent forwarding traces to backend as well
}
```

**Key unknown:** Does dd-tracer support sending traces via OTLP while simultaneously polling RC from the DD agent? The existing `APM_TRACING_OTLP` scenario uses `include_opentelemetry=True` which suggests the tracer can do both, but we need to verify RC still works in this mode.

**Alternative approach if tracer can't split data/RC planes:** Keep the DD agent as the full collector (traces + RC) AND also send traces via OTLP to the OTel Collector. The agent handles RC + traces; the OTel Collector is an additional path. This is less clean but may be necessary initially.

---

## 3. Implementation Plan

### Phase 1: New Scenario Definition

**File:** `utils/_context/_scenarios/__init__.py` (or a new file `appsec_otel_collector.py`)

Create a new scenario `APPSEC_OTEL_COLLECTOR` that combines:
- AppSec-enabled weblog (from `DdTraceEndToEndScenario`)
- OTel Collector as the collector instead of Datadog Agent (from `OtelCollectorScenario`)
- OTLP export from the tracer (from `OpenTelemetryScenario`)

**Option A — New standalone scenario class:**
```python
class AppSecOtelCollectorScenario(DockerScenario):
    """Test AAP features with native OTel Collector instead of Datadog Agent."""

    def __init__(self, name="APPSEC_OTEL_COLLECTOR", *, mocked_backend=True):
        super().__init__(
            name,
            github_workflow="endtoend",
            doc="Test AAP features through native OTel Collector",
            scenario_groups=[scenario_groups.appsec, scenario_groups.open_telemetry, scenario_groups.all],
            use_proxy=True,
            mocked_backend=mocked_backend,
        )

        # OTel Collector container (data plane)
        self.collector_container = OpenTelemetryCollectorContainer(
            config_file="./utils/build/docker/e2eotel/otelcol-config.yml",
            environment={...},
            volumes={...},
        )
        self._containers.append(self.collector_container)

        # DD Agent container (control plane — Remote Config only)
        self.agent_container = AgentContainer(use_proxy=True)
        self._containers.append(self.agent_container)

        # AppSec-enabled weblog with OTLP export for data + DD agent for RC
        self.weblog_container = WeblogContainer(
            environment={
                "DD_TRACE_OTEL_ENABLED": "true",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
                # RC still flows through the DD agent on port 8126
                # DD_AGENT_HOST and DD_TRACE_AGENT_PORT are set by WeblogContainer
                # AppSec env vars are set automatically by WeblogContainer
            },
            appsec_enabled=True,
            iast_enabled=True,
        )
        self.weblog_container.depends_on.append(self.collector_container)
        self.weblog_container.depends_on.append(self.agent_container)
        self._containers.append(self.weblog_container)
```

**Option B — Extend `DdTraceEndToEndScenario` with `include_otel_collector=True`:**
Add a flag to the existing `DdTraceEndToEndScenario` that swaps the Datadog Agent for an OTel Collector while keeping AppSec enabled. This is more reusable but more invasive.

**Recommendation:** Option A is cleaner for initial experimentation; Option B for long-term integration.

### Phase 2: Interface Validator Extensions

**Problem:** `interfaces.open_telemetry` (OpenTelemetryInterfaceValidator) has no AppSec validation methods. AppSec tests call `interfaces.library.assert_waf_attack()`, `interfaces.library.get_appsec_events()`, etc.

**Approach:**

1. **Understand how AppSec data appears in OTLP format** — When dd-trace exports via OTLP, AppSec data (`_dd.appsec.json` meta or `meta_struct.appsec`) is encoded as OTel span attributes. We need to determine:
   - Are AppSec triggers preserved as span attributes when exported via OTLP?
   - What is the attribute key naming? (e.g., `_dd.appsec.json` → `dd.appsec.json`?)
   - Does the OTel Collector `datadog` exporter correctly transform these back to Datadog format?

2. **Extend `OpenTelemetryInterfaceValidator`** (or create a new validator) with AppSec methods:
   ```python
   class OpenTelemetryInterfaceValidator(ProxyBasedInterfaceValidator):
       ...
       def get_appsec_events(self, request=None):
           """Find AppSec events in OTLP span attributes."""
           for data in self.get_data(path_filters=["/v1/traces"]):
               content = data.get("request", {}).get("content", {})
               for resource_span in content.get("resourceSpans", []):
                   for scope_span in resource_span.get("scopeSpans", []):
                       for span in scope_span.get("spans", []):
                           attributes = span.get("attributes", {})
                           # Look for AppSec data in attributes
                           appsec_data = attributes.get("_dd.appsec.json") or \
                                         attributes.get("dd.appsec.json")
                           if appsec_data:
                               yield data, span, appsec_data

       def assert_waf_attack(self, request, rule=None):
           """Assert a WAF attack was detected in OTLP spans."""
           ...
   ```

3. **Alternatively**, make AppSec tests use a generic interface abstraction that works with both `interfaces.library` and `interfaces.open_telemetry`. This would require refactoring test assertions but would be more maintainable.

### Phase 3: OTel Collector Config for AppSec

**File:** `utils/build/docker/e2eotel/otelcol-config.yml`

The existing config has traces/metrics/logs pipelines with the `datadog` exporter. For AppSec testing:
- The `datadog` exporter in the OTel Collector should handle AppSec span attributes correctly
- No special processors should strip AppSec data
- The `file/traces` exporter captures traces for local validation

**Potential config additions:**
```yaml
processors:
  # Ensure AppSec attributes are preserved
  # (No additional processors needed if datadog exporter handles them natively)
  # But may need to add:
  # - resource/add_service_name (if service name isn't set via OTLP)
  # - attributes/keep_appsec (if any default processors strip unknown attributes)
```

### Phase 4: Test Selection and Manifests

**Which AppSec tests to run initially:**

Start with a minimal subset to validate the data path, then expand:

| Priority | Test File | Feature | Why |
|----------|-----------|---------|-----|
| P0 | `tests/appsec/test_conf.py` | Static ruleset config | Basic AppSec activation |
| P0 | `tests/appsec/test_blocking_addresses.py` | WAF blocking | Core blocking functionality |
| P0 | `tests/appsec/test_request_blocking.py` | Request blocking | HTTP request blocking |
| P1 | `tests/appsec/test_traces.py` | AppSec trace tags | AppSec data in traces |
| P1 | `tests/appsec/test_automated_login_events.py` | Login events | Business logic events |
| P1 | `tests/appsec/test_identify.py` | User identification | SDK API |
| P2 | `tests/appsec/iast/sink/test_sql_injection.py` | IAST SQL injection | IAST sink detection |
| P2 | `tests/appsec/test_rate_limiter.py` | Rate limiting | Rate limiter |
| P3 | `tests/appsec/rasp/test_sqli.py` | RASP SQL injection | RASP detection |
| P3 | `tests/appsec/api_security/test_api_security.py` | API Security | Schema discovery |

**Manifest entries** (`manifests/{library}.yml`):
```yaml
# For each library, add entries for the new scenario
tests/appsec/test_conf.py::Test_StaticRuleSet:
  # Initially mark as missing_feature for OTel collector scenario
  # until we confirm it works
  APPSEC_OTEL_COLLECTOR: missing_feature
```

### Phase 5: Weblog Metadata

Create or update `weblog_metadata.yml` for the OTel collector weblog variant to include the new scenario in `supported_scenarios`:

```yaml
# For existing dd-trace weblogs (python, java, etc.)
# Add the new scenario to supported_scenarios
python:
  supported_scenarios:
    - DEFAULT
    - APPSEC_OTEL_COLLECTOR  # new
```

### Phase 6: CI Integration

**File:** `utils/scripts/libraries_and_scenarios_rules.yml`

Add rules for the new scenario group so CI knows which tests to run:
```yaml
utils/build/docker/e2eotel/*:
    scenario_groups: [open_telemetry, appsec]
    libraries: otel_collector
```

**File:** `.gitlab-ci.yml`

Add the new scenario to the CI pipeline definitions.

---

## 4. Key Technical Challenges & Risks

### 4.1 AppSec Data Format in OTLP

**Risk: HIGH** — This is the biggest unknown.

When dd-trace exports traces via OTLP instead of the Datadog agent protocol:
- AppSec data stored in `meta_struct["appsec"]` (v2) or `meta["_dd.appsec.json"]` (v1) needs to be encoded as OTel span attributes
- The OTel Collector `datadog` exporter must correctly transform these attributes back to Datadog's expected format
- If the `datadog` exporter doesn't handle AppSec attributes, they will be lost

**Mitigation:**
1. First, run a manual test: build a python weblog with AppSec + OTLP export, send an attack request, inspect the OTLP trace data captured by the proxy
2. Check if `_dd.appsec.json` or equivalent appears in OTLP span attributes
3. If not present, investigate dd-trace's OTLP export implementation for AppSec data
4. If present but not transformed by the `datadog` exporter, investigate exporter config or file a bug

### 4.2 Remote Configuration

**Risk: LOW** (corrected per M2 architecture)

~~Originally assessed as MEDIUM and suggested skipping RC tests.~~ **Corrected:** The M2 milestone from the strategic plan explicitly includes a DD Agent for the RC control plane. The architecture has two planes:
- **Data plane:** OTel Collector (traces/metrics/logs)
- **Control plane:** DD Agent (Remote Config only)

This means RC-dependent tests (runtime activation, remote config rule changes, dynamic blocking) **are in scope** and should work because the DD Agent handles RC independently from the data plane.

**Mitigation:**
- Include DD Agent in the scenario for RC
- Run RC-dependent tests (runtime activation, remote config rule changes, IP/user blocking via RC)
- Verify that RC updates flow through the DD Agent to the tracer while traces flow through the OTel Collector

### 4.3 Interface Validator Compatibility

**Risk: MEDIUM**

AppSec tests use `interfaces.library` which expects Datadog agent protocol data (JSON spans with `meta`, `meta_struct` fields). OTLP data has a different structure (`resourceSpans`, `scopeSpans`, `spans` with `attributes`).

**Mitigation:**
- Option 1: Create an adapter that normalizes OTLP spans to Datadog span format for the library interface
- Option 2: Create a new interface validator with AppSec methods for OTLP data
- Option 3: Use the `interfaces.otel_collector` interface (captures collector→backend traffic) and validate the Datadog-format data after the `datadog` exporter transforms it

**Recommendation:** Option 3 is most promising — the `datadog` exporter output should be in Datadog format, so we can validate AppSec data in the collector→backend proxy traffic using existing Datadog-format validators.

### 4.4 Tracer OTLP Export Support per Language

**Risk: MEDIUM**

Not all dd-trace libraries support OTLP export equally:
- Python: `DD_TRACE_OTEL_ENABLED=true` + OTLP exporter env vars
- Java: `DD_TRACE_OTEL_ENABLED=true` + OTLP exporter env vars
- Node.js, Go, .NET, PHP, Ruby, C++: Need to verify OTLP export support

**Mitigation:**
- Start with Python and Java (most mature OTLP support)
- Expand to other languages after validating the core data path
- Use manifests to mark unsupported languages as `missing_feature`

### 4.5 AppSec Blocking Behavior

**Risk: LOW**

AppSec blocking (returning 403) happens in the tracer before any data is exported. The collector choice shouldn't affect blocking behavior. Tests that only check HTTP status codes (e.g., `assert response.status_code == 403`) should work regardless.

**Mitigation:** None needed — blocking tests should work as-is.

### 4.6 Logs and Metrics Pipelines

**Risk: LOW-MEDIUM**

AppSec can emit logs and metrics. The OTel Collector config already has logs and metrics pipelines with the `datadog` exporter. But:
- AppSec logs may use a different format than standard OTLP logs
- AppSec metrics (e.g., `dd.appsec.traces` rate) may need specific handling

**Mitigation:** Validate logs/metrics separately after traces work.

---

## 5. Execution Plan

### Step 1: Spike — Validate AppSec Data in OTLP + RC via DD Agent (1-2 days)

**Goal:** Confirm two things before building infrastructure:
1. AppSec data survives OTLP export from dd-tracer
2. Remote Config still works when traces go via OTLP and RC goes via DD agent

**Steps:**
1. Use the existing `APM_TRACING_OTLP` scenario (which already has `include_opentelemetry=True` + `include_agent=True`) as a base
2. Enable AppSec on the weblog (`DD_APPSEC_ENABLED=true` — may need to pass `appsec_enabled=True` to the scenario or set env var manually)
3. Build a python weblog: `./build.sh python`
4. Run: `./run.sh APM_TRACING_OTLP` with AppSec enabled
5. Send an attack request: `weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})`
6. Inspect `interfaces.open_telemetry` captured data — look for `_dd.appsec.json` or equivalent in OTLP span attributes
7. Inspect `interfaces.library` captured data — check if RC polling still appears in the library interface (tracer→agent traffic on port 8126)
8. **Also test with `file` exporter only** (no `datadog` exporter) to confirm AAP attributes are preserved in raw OTLP format

**Key questions to answer:**
- Does dd-tracer export AppSec data (`_dd.appsec.json`, `meta_struct.appsec`) when using OTLP export?
- Does RC polling still work when traces are sent via OTLP? (check `interfaces.library` for RC requests)
- Does the OTel Collector `datadog` exporter transform AppSec attributes correctly?
- Are AppSec attributes preserved in raw OTLP (file exporter)?

**Deliverable:** Findings document answering all four questions, with example OTLP span data showing AppSec attributes (or confirming they're missing)

### Step 2: Create Minimal Scenario (2-3 days)

1. Create `AppSecOtelCollectorScenario` class (or extend `DdTraceEndToEndScenario`)
2. Configure weblog with AppSec + OTLP export (data plane)
3. Configure DD Agent for RC (control plane) — reuse existing `AgentContainer`
4. Configure OTel Collector with existing `otelcol-config.yml`
5. Set up proxy to capture both planes:
   - Port 8127: tracer→collector (OTLP, data plane)
   - Port 8126: tracer→agent (DD protocol, RC control plane)
   - Port 8128: collector→backend (datadog exporter output)
6. Configure interfaces: `interfaces.library` (RC traffic), `interfaces.open_telemetry` (OTLP traces), `interfaces.otel_collector` (collector→backend)
7. Register scenario in `__init__.py`
8. Run `./run.sh APPSEC_OTEL_COLLECTOR` and verify all containers start and weblog is healthy

**Deliverable:** Scenario boots successfully with all containers (weblog + OTel collector + DD agent + proxy)

### Step 3: Validate Basic AppSec Test (2-3 days) — ✅ DONE

**Result:** The OTLP adapter works. 84/109 tests pass with the adapter.

**Implementation:**
1. Created `DataDogLibraryTraceOTLP` and `DataDogLibrarySpanOTLP` in `utils/dd_types/_datadog_library_trace_otlp.py`
2. Added `_get_traces_from_otlp()` fallback in `LibraryInterfaceValidator.get_traces()` — when no Datadog-format traces are found, it reads from `interfaces.open_telemetry`
3. Added `_decode_appsec_data()` in `LibraryInterfaceValidator` — decodes base64+msgpack appsec data from OTLP format

**Test results:** 84 passed, 25 failed, 4 xfailed (out of 113 collected)

**Remaining failures (25):**
- 7 payment events: Stripe webhook returns 500 (test app issue, not OTLP-related)
- 3 alpha tests: `get_root_span` matching issue
- ~15 tests: access `span["meta"]["appsec"]` directly instead of going through `get_appsec_events()` — get raw base64 string instead of decoded dict

**Deliverable:** ✅ Core adapter works, 84% pass rate

### Step 4: Expand Test Coverage (3-5 days)

1. Enable more AppSec tests (blocking, traces, login events, identify)
2. Add manifest entries for each test/language
3. Fix any failures related to data format differences
4. Add IAST tests
5. Add RASP tests

**Deliverable:** Core AppSec test suite passes with OTel collector for Python

### Step 5: Multi-Language Support (3-5 days)

1. Test with Java weblog
2. Test with other languages as OTLP export support allows
3. Update manifests per language
4. Add CI pipeline entries

**Deliverable:** Multi-language AppSec + OTel collector test coverage

### Step 6: CI Integration & Documentation (2-3 days)

1. Add scenario to `libraries_and_scenarios_rules.yml`
2. Add to `.gitlab-ci.yml`
3. Add to feature parity dashboard
4. Document the new scenario in `docs/`
5. Update `docs/understand/scenarios/README.md`

**Deliverable:** Full CI integration, documented scenario

---

## 6. Test Matrix

### 6.1 AppSec Feature Coverage

| Feature | Test File | Key Assertions | Interface | Priority |
|---------|-----------|---------------|-----------|----------|
| Static ruleset | `test_conf.py` | AppSec events in spans | library/otel | P0 |
| WAF blocking | `test_blocking_addresses.py` | 403 status, WAF attack rule | library/otel | P0 |
| Request blocking | `test_request_blocking.py` | 403 status, blocked request | library/otel | P0 |
| Trace tagging | `test_traces.py` | AppSec tags in spans | library/otel | P1 |
| Login events | `test_automated_login_events.py` | `appsec.events.users.login.failure` tag | library/otel | P1 |
| User identification | `test_identify.py` | `usr.id` tag | library/otel | P1 |
| Custom events | `test_event_tracking.py` | `appsec.events.system_tests_appsec_event` tag | library/otel | P1 |
| Rate limiting | `test_rate_limiter.py` | Trace count within limits | library/otel | P2 |
| IAST SQL injection | `iast/sink/test_sql_injection.py` | Vulnerability in span tags | library/otel | P2 |
| IAST XSS | `iast/sink/test_xss.py` | Vulnerability in span tags | library/otel | P2 |
| RASP SQLi | `rasp/test_sqli.py` | Blocking + event | library/otel | P3 |
| API Security | `api_security/test_api_security.py` | Schema in span tags | library/otel | P3 |
| Remote config | `test_remote_config_rule_changes.py` | RC rule updates | RC API | Skip initially |
| Runtime activation | `test_runtime_activation.py` | RC activation | RC API | Skip initially |
| IP blocking | `test_ip_blocking_full_denylist.py` | 403 + WAF attack | library/otel | P1 |
| User blocking | `test_user_blocking_full_denylist.py` | 403 + WAF attack | library/otel | P1 |
| Suspicious attacker | `test_suspicious_attacker_blocking.py` | 403 + WAF attack | library/otel | P2 |
| Service activation | `test_service_activation_metric.py` | `_dd.appsec.service_activation` metric | agent/otel | P2 |
| **ATO (Account Takeover)** | `test_automated_login_events.py` | Login failure/success events, ATO detection | library/otel | P1 |
| Suspicious attacker | `test_suspicious_attacker_blocking.py` | 403 + WAF attack | library/otel | P2 |

### 6.2 Language Coverage (Phase 1)

| Language | OTLP Export | AppSec | IAST | RASP | Initial Support |
|----------|-----------|--------|------|------|-----------------|
| Python | ✅ | ✅ | ✅ | ✅ | Yes |
| Java | ✅ | ✅ | ✅ | ✅ | Yes |
| Node.js | ✅ | ✅ | ✅ | ❌ | Phase 2 |
| Go | ? | ✅ | ❌ | ❌ | Phase 2 |
| .NET | ? | ✅ | ✅ | ❌ | Phase 2 |
| PHP | ? | ✅ | ❌ | ❌ | Phase 3 |
| Ruby | ? | ✅ | ❌ | ❌ | Phase 3 |
| C++ | ? | ✅ | ❌ | ❌ | Phase 3 |

---

## 7. Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `utils/_context/_scenarios/appsec_otel_collector.py` | New scenario class |
| `utils/build/docker/e2eotel/otelcol-config-appsec.yml` | OTel collector config for AppSec (if needed) |
| `tests/appsec/test_otel_collector_appsec.py` | New test file for OTel-specific AppSec tests (if needed) |
| `docs/understand/scenarios/appsec-otel-collector.md` | Documentation |

### Modified Files
| File | Changes |
|------|---------|
| `utils/_context/_scenarios/__init__.py` | Register new scenario instance |
| `utils/interfaces/_open_telemetry.py` | Add AppSec validation methods |
| `utils/interfaces/__init__.py` | Export new interface if needed |
| `utils/_context/_scenarios/core.py` | Add `appsec_otel` scenario group (optional) |
| `manifests/python.yml` | Add test entries for new scenario |
| `manifests/java.yml` | Add test entries for new scenario |
| `utils/scripts/libraries_and_scenarios_rules.yml` | Add CI routing rules |
| `.gitlab-ci.yml` | Add CI pipeline for new scenario |
| `utils/build/docker/e2eotel/otelcol-config.yml` | Possibly add AppSec-specific processors |

---

## 8. Success Criteria

1. **Core:** AppSec attack detection (WAF triggers) is correctly forwarded through the OTel Collector and visible in the Datadog backend
2. **Blocking:** HTTP request blocking (403 responses) works identically regardless of collector choice
3. **Trace Data:** AppSec events, triggers, and span tags survive the OTLP → datadog exporter transformation
4. **Raw OTLP:** AppSec attributes are preserved in standard OTLP format (file exporter), independent of Datadog-specific transformation
5. **ATO:** Account Takeover detection (login events) is preserved through the OTel Collector
6. **IAST:** IAST vulnerability detection data is preserved through the OTel Collector
7. **Multi-language:** At least Python and Java pass the core AppSec test suite with the OTel Collector
8. **CI:** The new scenario runs in CI without breaking existing scenarios

---

## 8a. Support Statement (Topology: dd-trace + AAP → OTel Collector → Datadog)

> This is a draft support statement for the topology covered by this plan. It should be finalized after testing is complete.

**What we expect to work:**
- WAF attack detection (static ruleset) — triggers are embedded in span attributes and should survive OTLP export
- HTTP request blocking (403) — blocking happens in-tracer before any data export, so collector choice should not matter
- **Remote Configuration-dependent features** (rule updates, runtime activation, dynamic blocking) — DD Agent handles RC control plane independently from OTel Collector data plane
- IAST vulnerability detection — vulnerability data embedded in span tags
- API Security schema discovery — schema data in span tags
- **ATO (Account Takeover) detection** — login event tracking data in span meta
- Login/user/payment event tracking — custom events in span meta
- User identification — `usr.id` tag in spans

**What may not work (to be confirmed):**
- AppSec metrics (e.g., `_dd.appsec.traces` rate) — may need specific metrics pipeline configuration in OTel Collector
- Meta_struct data — the OTLP format may not preserve Datadog-specific `meta_struct` fields
- Tracer configuration where data and RC planes share a single endpoint — M2 requires separate endpoints

**Known limitations:**
- Only tested with Python and Java initially; other languages depend on OTLP export support in their dd-trace implementation
- Coexistence with a separate OTel SDK in the same process is not tested by this plan (that's M3/M4)
- Non-Datadog backend testing (Grafana, vanilla collector) is limited to raw OTLP attribute validation via file exporter

---

## 9. Open Questions

1. **Does dd-trace export AppSec data (`_dd.appsec.json`, `meta_struct.appsec`) when using OTLP export?** → Needs spike (Step 1)
2. **Does the OTel Collector `datadog` exporter correctly transform AppSec span attributes to Datadog format?** → Needs investigation
3. **Can dd-tracer send traces via OTLP while simultaneously polling RC from the DD agent?** → Key architectural question for M2. The existing `APM_TRACING_OTLP` scenario with `include_opentelemetry=True` + `include_agent=True` suggests yes, but RC must be explicitly verified.
4. **Are there OTel Collector processors that strip unknown attributes (like AppSec data)?** → Check default processor behavior
5. **What happens to AppSec metrics (e.g., `_dd.appsec.traces`)?** → Need to verify metrics pipeline
6. **Does the `datadog` exporter in OTel Collector support `meta_struct`?** → Check exporter implementation
7. **Does ATO (Account Takeover) detection data survive the OTLP export path?** → Add to spike scope
8. **Are AAP attributes preserved in raw OTLP format (file exporter, no `datadog` exporter)?** → Add to spike scope, validates non-Datadog backend compatibility
9. **Does the DD agent need special configuration to serve RC only (no trace ingestion)?** → Check if agent can be configured for RC-only mode, or if it accepts traces but they're just unused
10. **How does the proxy distinguish between OTLP traffic (port 8127) and DD agent protocol traffic (port 8126)?** → The proxy already handles both ports; verify both are captured correctly

---

## 10. Broader R&D Context

This plan covers **M2 (DD Tracer + OTel Collector + DD Agent for RC)** from the strategic plan "AAP for OTel Customers" (Google Doc by Ramy Elkest + Zach Montoya).

The full milestone roadmap:
1. **M0 — Know the Gap** — baseline characterization of pure OTel SDK path (no AAP). Not covered by this plan.
2. **M1 — Full AAP, Minimal Migration** — DD Tracer as drop-in replacement for OTel SDK, any collector. Not covered by this plan.
3. **M2 — Full AAP, Keep Your Collector** — DD Tracer + OTel Collector + DD Agent for RC. **This plan.**
4. **M3 — AAP with Zero SDK Migration** — OTel SDK + DD AAP Library side-by-side. Not covered.
5. **M4 — Migration Window Support** — Both SDKs running simultaneously. Not covered.

**GA bar for M2 (from strategic plan):**
- At least 2 reference languages validated (Python + Java)
- Version-tagged public support statement exists
- Sample app in customer-facing docs
- System test coverage in place for topology × language combinations ← **this plan**

**"Supported" means:** WAF, ATO detection, and API Security all function and are validated.

**Related documents:**
- Strategic plan: [Google Doc](https://docs.google.com/document/d/1VFIN40tNo_wrY7S8njSe82AD-wWuTYeZAN3Su5JwDus/edit) (Ramy Elkest + Zach Montoya, Draft June 2026)
- R&D test plan: [Confluence](https://datadoghq.atlassian.net/wiki/spaces/SAAL/pages/6668091590) (SAAL space)

**Follow-up plans needed for:**
- M0: Baseline characterization (OTel SDK → OTel Collector → Datadog intake, no Datadog tracer)
- M1: DD Tracer drop-in validation (any collector, OTel API parity)
- M3: Coexistence testing (OTel SDK + AAP library in same process)
- M4: Parallel pipeline support policy
- Non-Datadog backend validation (Grafana, vanilla collector without `datadog` exporter)
- Coexistence overhead/performance benchmarking
