## What is "System tests"?

System tests is a test workbench that allow any kind of functional testing over libraries (AKA tracers) and agents. It's build with several key principles:

* *Black box testing*: only component's interfaces are checked. As those interface are very stable, our tests 
* *No test isolation*: Yes, it's surprising. But it allows to be very fast. So never hesitate to add a new test. And if you need a very specific test case, we can run it separately.

## How to run them locally?

You will only need `docker-compose`. It's basiccaly cloning this repo, create a `.env` file with `DD_API_KEY=<a_valid_staging_api_key>` and run two commands. Please have a look at the [execution documentation](./execute).

## How to add them on a CI?

Depending on your CI, it may be more or less easy. The steps are almost the same than a local run. You can find complete documentation in our [CI documentation](./CI).

## How to add a new test case?

The workflow is very simple: add your test case, commit into a branch and create a PR. We'll review it ASAP. That being said, you may have a look on our [edition documentation](./edit).
