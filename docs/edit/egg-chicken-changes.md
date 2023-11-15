As system-tests lives in a different repo, testing a new feature before merging it is not as straightforward as if the test suite was in your own repo. You must make your changes on both repo, and, if we were in a perfect world, merge them simultaneously.

We are not in a perfect world, so here is the recipes :

## The very lazy way

1. Do your PR in your repo, merge it
2. Do the PR on system-tests, merge it

Totally acceptable, if you accept the risk to do another PR on your repo.

## The lazy way (but probably the best one)

1. Do a PR in system-tests (it fails)
2. Do your PR in your repo
3. Test it locally
4. Merge your PR on your repo
5. Re-run system-tests PR. In theory, it should be ok.
6. Merge it

You have to run system-tests locally. But you will reduces the risk of rework on your repo, and you keep your `main` branch clean.

## The good way (actually good only if you don't need to modify the test)

Use the [`-F` option](../execute/force-execute.md):

1. If needed, add the test in system tests, skip it using manifest, merge this PR
2. Do your PR in your repo
3. Modify your CI to include the test you want to activate:
    * `./run.sh MY_SCENARIO -F tests/feature.py::Test_Feature`
3. Iterate on your PR, merge it
4. :warning: Add a PR in system-tests repo to unskip the test in manifest file, otherwise we may change the test, and break your CI without noticing it.

And so time to time, removes all the `-F` in your CI.

## The good way (but so heavy, it's probably not worthy)

1. Do a PR in system-tests (it fails)
2. Do your PR in your repo. **On this PR, change the CI to use the system-tests branch**
3. Iterate on both PR until the PR on your repo is ok
4. Very last commit on your PR : **revert the change on your CI that used the dedicated system-tests branch**
5. Merge your PR on your repo
6. Re-run system-tests PR CI. In theory, it should be ok.
7. Merge it.
