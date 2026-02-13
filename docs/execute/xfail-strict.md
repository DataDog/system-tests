If a test is flagged as `missing_feature` or `bug`, the test is disabled but still executed (see [glossary](../glossary.md) for terminology):

* if it is unsuccessful → xfail (result is ignored)
* if it is successful → xpass (easy win), a warning is printed but it does not fail the entire process

For some reason, you may want to have the process fail if there is an xpass. To achieve that, add the `-o xfail_strict=True` option to the `./run.sh` command.

Though, you must be careful if you use this option in your CI. As system-tests are continuously updated with new tests, and by default, missing_feature is added on all languages, your CI may be broken suddenly. So it's strongly recommended to pin the system-tests version in your CI if you want to use this option.

For this same reason, this option is **not** used in system-tests CI.

Though, it's recommended to use this option in your release process, to guarantee that you don't have forgotten tests. The page [Easy-Wins page on Feature Parity Dashboard](https://feature-parity.us1.prod.dog/#/easy-wins) is also a convenient way to track those xpass (easy wins).