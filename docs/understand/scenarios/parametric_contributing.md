# Contributing to Parametric System-tests

Note: a more in-depth overview of parametric system-tests can be found in [parametric.md](parametric.md).

**MUST:** Acquaint yourself with [how system tests work](parametric.md#architecture-how-system-tests-work) before proceeding.

## Use cases

Let's figure out if your feature is a good candidate to be tested with parametric system-tests.

System-tests in general are great for assuring uniform behavior between different dd-trace repos (tracing, ASM, DI, profiling, etc.). There are two types of system-tests, [end-to-end](/docs/README.md) and [parametric](/docs/understand/scenarios/parametric.md).

Parametric tests in the Datadog system test repository validate the behavior of APM Client Libraries by interacting only with their public interfaces. These tests ensure the telemetry generated (spans, metrics, instrumentation telemetry) is consistent and accurate when libraries handle different input parameters (e.g., calling a Tracer's startSpan method with a specific type) and configurations (e.g., sampling rates, distributed tracing header formats, remote settings). They run against web applications written in Ruby, Java, Go, Python, PHP, Node.js, C++, and .NET, which expose endpoints simulating real-world ddtrace usage. The generated telemetry is sent to a Datadog agent, queried, and verified by system tests to confirm proper library functionality across scenarios.

If your usage does not require different parameter values, then [end-to-end system-tests](/docs/README.md) should be used as they will achieve the same level of behavior uniformity verification and test the feature on real world use cases, catching more issues. End-to-end tests are also what should be used for verify behavior between tracer integrations.
For more on the differences between end-to-end and parametric tests, see [here](/docs/understand/scenarios/README.md#scenarios)
System-tests are **not** for testing internal or niche library behavior. Unit tests are a better fit for that case.

## Getting set up

We usually add new system tests when validating a new feature. To begin, set up the system-tests repo to run with a version of the library that has already implemented the feature you'd like to test (published or on a branch).
Follow [Binaries Documentation](../../run/binaries.md) for your particular tracer language to set this up.

[Verify that you can run some (any) parametric tests with your custom tracer](parametric.md#running-the-tests). Make sure some pass — no need to run the whole suite (you can stop the tests from running with `ctrl+c`). If you have any issues, checkout the [debugging section](parametric.md#debugging) to troubleshoot.

## Writing the tests

Now that we're all setup with a working test suite and a tracer with the implemented feature, we can begin writing the new tests.

**MUST:** If you haven't yet, please acquaint yourself with [how system tests work](parametric.md#architecture-how-system-tests-work) before proceeding and reference it throughout this section.

Before writing a new test, check the [existing tests](/tests/parametric) to see if you can use the same methods or endpoints for similar scenarios; in many cases, new endpoints do not need to be added.

For a list of client methods that already exist, refer to `class APMLibrary` in the [_library_client.py](/utils/parametric/_library_client.py). If you're wondering what the methods do, you can take at look at the respective endpoints they're calling in that same file in `class APMLibraryClient`.

The endpoints (where the actual tracer code runs) are defined in the Http Server implementations per tracer [listed here](parametric.md#http-server-implementations). Click on the one for your language to take a look at the endpoints. In some cases you may need to just slightly modify an endpoint rather than add a new one.

### If you need to add additional endpoints to test your new feature

*Note:* please refer to the [architecture section](parametric.md#architecture-how-system-tests-work) if you're confused throughout this process.

Then we need to do the following:

* Determine what you want the endpoint to be called and what you need it to do, and add it to your tracer's http server.

*Note:* If adding a new endpoint please let a Python tracer implementer know so they can add it as well [see](parametric.md#shared-interface)
*Note*: Only add new endpoints that operate on the public API and execute ONE operation. Endpoints that execute complex operations or validate tracer internals will not be accepted.
* In [_library_client.py](/utils/parametric/_library_client.py) Add both the endpoint call in `class APMLibraryClient` and the method that invokes it in `class APMLibrary`. Use other implementations for reference.

* Ok we now have our new method! Use it in the tests you write using the [below section](#if-the-methods-you-need-to-run-your-tests-are-already-written)

### If the methods you need to run your tests are already written

If it makes sense to add your tests to a file that already exists, great! Otherwise make a new test file in `tests/parametric`.

Next copy the testing code you want to use as a base/guideline (usually the class (if using a new file) and one of the test methods in it).

Then:

* [Change the name of the feature annotation it'll fit under for the feature parity board](/docs/write/features.md) (Not always needed e.g. `@features.datadog_headers_propagation` is used for all the propagation features)
* Change the class and method name to fit what you're testing.
* [Change your tracer's respective manifest.yml file](/docs/write/manifest.md) or else the script won't know to run your new test. If you're confused at how to do this properly, search for the file you copied the test from in the manifest file and see how it's specified, you can probably copy that for your new file (make sure the path is the same).
For the version value, to make sure your test runs, specify the current release your tracer is on. This is the minimum value that the script will run your test with. If you make it too high, the script will skip your test.
* Write the test pulling from examples of other tests written. Remember you're almost always follwing the pattern of making spans, getting them from the trace_agent, and then verifying values on them.

**Finally:**
[Try running your test!](parametric.md#running-the-tests)
If you have an issue, checkout the [debugging section](parametric.md#debugging) to troubleshoot.
