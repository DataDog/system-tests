# Contributing to Parametric System-tests

Note: a more in-depth overview of parametric system-tests can be found in [parametric.md](parametric.md).

## Use cases

Let's figure out if your feature is a good candidate to be tested with parametric system-tests. Parametric system-tests are great for assuring uniform behavior between tracers e.g. environment variable configuration effects, sampling, propagation.

Parametric system-tests are horrible for testing internal tracer behavior or testing niche tracer behavior. Tests for those should exist on the tracer repos since they're only applicable for that specific tracer.

## How to write some parametric tests

Usually the system-tests writer is writing for a new feature, potentially one that hasn't been completed across all tracers yet. Therefore they'll want to focus on writing and getting the tests to pass for their tracer first.

To begin we need to point system-tests towards a tracer that has the feature implemented (published or on a branch). Follow [Binaries Documentation](../execute/binaries.md) for your particular language to set this up.

Now that we can test against a tracer that has the feature let's 