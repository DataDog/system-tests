When making changes to dd-trace, you'll commonly need to run the unmerged changes against the system tests (to ensure the feature is up tospec). But because system tests are outside of the dd-trace repo, testing against unmerged changes is not so straightforward. Various approaches  to this "chicken or the egg" problem are detailed below.

## The common way (Suitable and recommended for most cases) 

This approach emphasises running system-tests locally. It assumes the necessary test already exists in system-tests and your weblog or parametric app has the necessary endpoint for serving the test [TODO]: LINK TO CONTRIBUTING DOC

1. Post a PR to the dd-trace repo
2. Post a PR to system-tests, enabling your test (it will fail in CI; the necessary change is not merged into dd-trace main yet) [TODO]: LINK TO CONTRIBUTING DOC
3. Test it locally
4. Merge dd-trace PR 
5. Re-run system-tests PR. It should be pass.
6. Merge system-tests PR


## The heavier way (actually good only if you don't need to modify the test)

Use the [`-F` option](../execute/force-execute.md):

1. If needed, add the test in system tests, skip it using manifest, merge this PR
2. Do your PR in your repo
3. Modify your CI to include the test you want to activate:
    * `./run.sh MY_SCENARIO -F tests/feature.py::Test_Feature`
3. Iterate on your PR, merge it
4. :warning: Add a PR in system-tests repo to unskip the test in manifest file, otherwise we may change the test, and break your CI without noticing it.

And so time to time, removes all the `-F` in your CI.

## The most robust way (but so heavy, it's probably not worthy)

1. Do a PR in system-tests (it fails)
2. Do your PR in your repo. **On this PR, change the CI to use the system-tests branch**
3. Iterate on both PR until the PR on your repo is ok
4. Very last commit on your PR : **revert the change on your CI that used the dedicated system-tests branch**
5. Merge your PR on your repo
6. Re-run system-tests PR CI. In theory, it should be ok.
7. Merge it.
