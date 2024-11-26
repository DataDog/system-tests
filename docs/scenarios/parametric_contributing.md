# Contributing to Parametric System-tests

Note: a more in-depth overview of parametric system-tests can be found in [parametric.md](parametric.md).

**MUST:** Acquaint yourself with [how system tests work](parametric.md#architecture-how-system-tests-work) before proceeding.

## Use cases

Let's figure out if your feature is a good candidate to be tested with parametric system-tests. 

Parametric system-tests are great for assuring uniform behavior between tracers e.g. [environment variable configuration effects on api methods, sampling, propagation, configuration, telemetry](/tests/parametric).

Parametric tests make requests to [http endpoints](/tests/parametric) dedicated to various tracer methods for creating and modifying spans (manual instrumentation). If you want to test automatic instrumentation behavior, weblog system-tests may be a better fit.

System-tests are **not** for testing internal or niche tracer behavior. Unit tests are a better fit for that case.

## Getting set up

We usually add new system tests when validating a new feature. This feature might not yet be implemented across all dd-trace libraries. If at least one library already supports the feature, you can verify your test by running it against that library.

To begin we need to make sure system-tests run with a tracer that has implemented the feature being tested (published or on a branch).
Follow [Binaries Documentation](../execute/binaries.md) for your particular tracer language to set this up.

[Verify that you can run some parametric tests with your custom tracer](parametric.md#running-the-tests). Make sure some pass (no need to run the whole suite, you can stop the tests from running with `ctrl+c`). If you have an issue, checkout the [debugging section](parametric.md#debugging) to troubleshoot.

## Writing the tests

Now that we're all setup with a working test suite and a tracer with the implemented feature, we can begin writing the new tests.

First take a look at the [currently existing tests](/tests/parametric), (available client calls)[], and corresponding [available http server endpoints](parametric.md#http-server-implementations) and see if what you're trying to test is similar and can use the same methods/endpoints (in many cases this is true).

For a list of client methods that already exist, refer to `class APMLibrary` in the [_library_client.py](/utils/parametric/_library_client.py). If you're wondering what the methods do, you can take at look at the respective endpoints they're calling in that same file in `class APMLibraryClient`.

The endpoints (where the actual tracer code runs) are defined in the Http Server implementations per tracer [listed here](parametric.md#http-server-implementations). Click on the one for your language to take a look at the endpoints. In some cases you may need to just slightly modify an endpoint rather than add a new one.

### If you need to add additional endpoints to test your new feature

*Note:* please refer to the [architecture section](parametric.md#architecture-how-system-tests-work) if you're confused throughout this process.

Then we need to do the following:

* Determine what you want the endpoint to be called and what you need it to do, and add it to your tracer's http server.

*Note:* If adding a new endpoint please let a Python implementer know so they can add it as well [see](parametric.md#shared-interface)
* In [_library_client.py](/utils/parametric/_library_client.py) Add both the endpoint call in `class APMLibraryClient` and the method that invokes it in `class APMLibrary`. Use other implementations for reference.
* Ok we now have our new method! Use it in the tests you write using the [below section](#if-the-methods-you-need-to-run-your-tests-are-already-written)

### If the methods you need to run your tests are already written

If it makes sense to add your tests to a file that already exists, great! Otherwise make a new test file in `tests/parametric`. 

Next copy the testing code you want to use as a base/guideline (usually the class (if using a new file) and one of the test methods in it).

Then:

* [Change the name of the feature annotation it'll fit under for the feature parity board](/docs/edit/features.md) (Not always needed e.g. `@features.datadog_headers_propagation` is used for all the propagation features)
* Change the class and method name to fit what you're testing.
* [Change your tracer's respective manifest.yml file](/docs/edit/manifest.md) or else the script won't know to run your new test. If you're confused at how to do this properly, search for the file you copied the test from in the manifest file and see how it's specified, you can probably copy that for your new file (make sure the path is the same).
For the version value, to make sure your test runs, specify the current release your tracer is on. This is the minimum value that the script will run your test with. If you make it too high, the script will skip your test.
* Write the test pulling from examples of other tests written. Remember you're almost always follwing the pattern of making spans, getting them from the trace_agent, and then verifying values on them.

**Finally:**
[Try running your test!](parametric.md#running-the-tests)
If you have an issue, checkout the [debugging section](parametric.md#debugging) to troubleshoot.
