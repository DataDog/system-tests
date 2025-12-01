Whether it's adding a new test or modifying an existing test, a moderate amount of effort will be required. The instructions below cater to end-to-end tests, refer to [the parametric contributing doc](/docs/scenarios/parametric_contributing.md)for parametric-specific instructions.

Once the changes are complete, post them in a PR.

#### Notes
* Each test class tests only one feature (see [the doc on features](https://github.com/DataDog/system-tests/blob/main/docs/edit/features.md))
* A test class can have several tests
* If an RFC for the feature exists, you must use the decorator `rfc` decorator:
```python
from utils import rfc


@rfc("http://www.claymath.org/millennium-problems")
class Test_Millenium:
    """ Test on small details """
```

In most cases, you'll only need to add a new test class or function. But if you need to add a new scenario, refer to [scenarios.md](./scenarios.md).

---

Tests live under the `tests/` folder. You may need to add a new file to this folder, or a new directory + file to this folder. Alternatively, you may add a test to an existing file, if it makes sense. Tests are structured like so, e.g. `tests/test_some_feature.py`:

```python
class Test_Feature():
    def optional_test_setup(self):
        my_var = 1
    def test_feature_detail(self):
        assert my_var + 1 == 2
```

## Weblog Requests and Interface Validation

The weblog apps are responsible for generating instrumentation. Your test should send a request to the weblog and inspect the response. There are various endpoints on weblogs for performing dedicated behaviors (e.g, starting a span, etc). When writing a new test, you might use one of the existing endpoints or create a new one if needed.

To validate the response from the weblog and ensure data flows correctly through the system, system-tests provides three powerful interface validators that intercept and validate data at different stages of the pipeline:

### Interface Validators Overview

```python
from utils import weblog, interfaces

class Test_Feature():
    def setup_feature_detail(self):
        self.r = weblog.get("/url")

    def test_feature_detail(self):
        """ tests an awesome feature """
        # Validate data at tracer-to-agent level
        interfaces.library.validate_spans(self.r, validator=lambda span: span["meta"]["http.method"] == "GET")

        # Validate data at agent-to-backend level
        interfaces.agent.assert_trace_exists(self.r)

        # Validate data reaches the backend and is searchable
        interfaces.backend.assert_library_traces_exist(self.r)
```

### Available Interface Validators

1. **Library Interface (`interfaces.library`)** - Validates messages between instrumented applications and the Datadog Agent
   - Intercepts raw tracer output before agent processing
   - Perfect for validating span content, AppSec events, telemetry, and remote configuration
   - See detailed methods: [Library Interface Validation Methods](../internals/library-interface-validation-methods.md)

2. **Agent Interface (`interfaces.agent`)** - Validates messages between the Datadog Agent and Datadog Backend
   - Intercepts data after agent processing (sampling, aggregation, transformation)
   - Ideal for validating metrics, stats, processed traces, and agent forwarding behavior
   - See detailed methods: [Agent Interface Validation Methods](../internals/agent-interface-validation-methods.md)

3. **Backend Interface (`interfaces.backend`)** - Validates data by querying Datadog's production APIs
   - Makes actual API calls to verify end-to-end data ingestion
   - Essential for validating search functionality and customer-visible data
   - Requires `DD_API_KEY` and `DD_APP_KEY` environment variables
   - See detailed methods: [Backend Interface Validation Methods](../internals/backend-interface-validation-methods.md)

### Common Validation Patterns

#### Basic Trace Validation
```python
def test_basic_tracing(self):
    r = weblog.get("/")

    # Ensure trace exists at library level
    interfaces.library.assert_trace_exists(r)

    # Validate specific span tags
    interfaces.library.add_span_tag_validation(r, tags={"http.method": "GET"})

    # Verify trace reaches backend
    interfaces.backend.assert_library_traces_exist(r)
```

#### AppSec Event Validation
```python
def test_waf_attack_detection(self):
    r = weblog.get("/", headers={"X-Attack": "' OR 1=1--"})

    # Validate WAF attack detection at library level
    interfaces.library.assert_waf_attack(r, rule="sqli-detection")

    # Ensure AppSec data reaches agent
    def appsec_validator(data, payload, chunk, span, appsec_data):
        return "triggers" in appsec_data
    interfaces.agent.validate_appsec(r, appsec_validator)
```

#### Custom Validation with Validators
```python
def test_custom_span_validation(self):
    r = weblog.get("/custom-endpoint")

    def service_validator(span):
        return span.get("service") == "my-custom-service"

    interfaces.library.validate_spans(r, validator=service_validator)
```

### Data Flow Understanding

Understanding where each interface validates data helps you choose the right validator:

```
[Tracer] → [Agent] → [Backend] → [APIs]
    ↑          ↑          ↑
Library    Agent     Backend
Interface  Interface Interface
```

- **Library Interface**: Raw tracer output, before any agent processing
- **Agent Interface**: Processed data being sent to backend (sampled, aggregated)
- **Backend Interface**: Final ingested data available through production APIs

Sometimes you need to [skip a test](./skip-tests.md):

```python
from utils import weblog, interfaces, context, bug


class Test_Feature():

    def setup_feature_detail(self):
        self.r = weblog.get("/url")

    @bug(library="ruby", reason="APPSEC-123")
    def test_feature_detail(self):
        """ tests an awesome feature """
        interfaces.library.validate_spans(self.r, validator=lambda span: span["meta"]["http.method"] == "GET")
```

You'll need to build the images at least once, so if you haven't yet, run the `build` command. After the first build, you can just re-run the tests using the `run` command.

- build: `build.sh <library_name> [options...]`, see [build documentation](../execute/build.md) for more info
- run: `./run.sh tests/test_some_feature.py::Test_Feature::test_feature_detail`, see [run documentation](../execute/run.md) for more info

You now have the basics. Expect to dive into the test internals, but feel free to ask for help on slack at [#apm-shared-testing](https://dd.slack.com/archives/C025TJ4RZ8X)
