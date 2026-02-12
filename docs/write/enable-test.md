## Where to begin

So, you have a branch that contains changes you'd like to test with system tests...

**Note**: the instructions below assume that the necessary test already exists in system-tests and your weblog or parametric app has the necessary endpoint for serving the test.

1. Post a PR to the dd-trace repo if you have not already.

2. Test system-tests changes locally

   Before enabling/disabling a test in CI, you'll need to test the changes locally.

   **Run the test locally against production-level code**:

   Enable the test to run on the latest version.
   If you know the specific release that contains the changes that allowed your lib to pass the test, and this release is not latest version, then use that version in the manifest. But don’t
   lose sleep hunting down the specific version if you don’t know it, just use the latest.

   **Run the test against unmerged or unreleased changes**:

   Follow [binaries.md](../run/binaries.md) to run the app with a custom build, then [update the manifest file](./manifest.md) with the name of your lib’s main branch (probably `v<next-minor-release>-dev`, see [versions.md](./versions.md)).

   By now, you should have a change to a manifest file. Post a PR to system-tests with your changes (the enabled test(s) will fail in CI if you enabled the test for the main branch; the necessary change is not merged into dd-trace main yet)

3. Merge changes into dd-trace

4. Re-run system-tests PR

   It should be pass. Assuming it does, merge system-tests PR.


---
## Alternative approaches

In most cases, you can ignore these.

### Approach \#1: Good only if you don't need to modify the test)

Use the [`-F` option](../run/force-execute.md):

1. If needed, add the test in system tests, skip it using manifest, merge this PR
2. Do your PR in your repo
3. Modify your CI to include the test you want to activate:
    * `./run.sh MY_SCENARIO -F tests/feature.py::Test_Feature`
3. Iterate on your PR, merge it
4. :warning: Add a PR in system-tests repo to unskip the test in manifest file, otherwise we may change the test, and break your CI without noticing it.

And so time to time, removes all the `-F` in your CI.

### Approach #2: The most robust way (but so heavy, it's probably not worthy)

1. Do a PR in system-tests (it fails)
2. Do your PR in your repo. **On this PR, change the CI to use the system-tests branch**
3. Iterate on both PR until the PR on your repo is ok
4. Very last commit on your PR : **revert the change on your CI that used the dedicated system-tests branch**
5. Merge your PR on your repo
6. Re-run system-tests PR CI. In theory, it should be ok.
7. Merge it.
