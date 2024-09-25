If a test is flagged as `missing_feature` or `bug`, the test will be executed and :

* if it fails, it will be ignored
* if it passes, a warning will be printed, with the mention XPASS, but it does not fail the entire process

For some reason, you may want to have the process to fail if there is a `XPASS`. To achieve that, add the `-o xfail_strict=True` option to the `./run.sh` command.

Though, you must be careful you if use this option in your CI. As system-tests are continuously updated with new tests, and by default, missing_feature are added on all languages, your CI may be broken suddendly. So it's strongly recommended to pin the system-tests version in your CI if you want to use this option.

For this same reason, this option is **not** used in system-tests CI.

Though, it's recommended to use this option in your release process, to guarantee that you don't have forgotten test. The page [Easy-Wins page on Feature Parity Dashbaord](https://feature-parity.us1.prod.dog/#/easy-wins) is also a convenient way to track those xpass.