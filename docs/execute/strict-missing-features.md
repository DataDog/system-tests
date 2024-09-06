If a test is flagged as `missing_feature`, the test will be executed and :

* if it fails, it will be ignored
* if it passes, a warning will be printed, with the mention XPASS, but it does not fail the entire process

For some reason, you may want to have the process to fail if a `missing_feature` passes. To achieve that, add the `--strict-missing-features` option to the `./run.sh` command.

Though, you must be careful you if use this option in your CI. As system-tests are continuously updated with new tests, and by default, missing_feature are added on all languages, your CI may be broken suddendly. So it's strongly recommended to pin the system-tests version in your CI if you want to use this option.

For this same reason, this option is **not** used in system-tests CI.