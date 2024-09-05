## What is "System tests"?

System tests is a test workbench that allows any kind of functional testing over libraries (AKA tracers) and agents. It's built with several key principles:

* *Black box testing*: only components' interfaces are checked. As those interfaces are very stable, our tests can make assertions without any assumptions regarding underlying implementations. "Check that the car moves, regardless of the engine"
* *No test isolation*: Yes, it's surprising. But it allows to be very fast. So never hesitate to add a new test. And if you need a very specific test case, we can run it separately.

## How to run them locally?

You will only need `docker-compose`. It's basically cloning this repo, create a `.env` file with `DD_API_KEY=<a_valid_staging_api_key>` and run two commands. Please have a look at the [execution documentation](./execute).

## How to add them to a CI?

Depending on your CI, it may be more or less easy. The steps are almost the same as a local run. You can find complete documentation in our [CI documentation](./CI).

## How to add a new test case?

The workflow is very simple: add your test case, commit into a branch and create a PR. We'll review it ASAP. That being said, you may have a look at our [edition documentation](./edit).
