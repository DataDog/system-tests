Test items are skipped (or not) based on declarations in tests class, using manifest, or @bug/flaky/missing_feature decorators.

This fact implies an [egg-chicken issue](../edit/egg-chicken-changes.md) if you need to work on a feature. A way to handle it is to use the `-F` option :

1. in your PR, modify your CI to include the test you want to activate:
   - `./run.sh MY_SCENARIO -F tests/feature.py::Test_Feature -F tests/feature.py::Test_FeatureEdgeCase`
1. iterate on your PR, merge it

:warning: Do not forget to add a PR in system-tests repo, otherwise we may change the test, and break your CI without noticing it.

And so time to time, removes all the `-F` in your CI.
