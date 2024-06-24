When a modification is made in system tests, the CI tries to detect which scenario to run :

1. based on modified files in `tests/`, by extracting scenarios targerted by those files
1. based on any modification in a `tests/**/utils.py`, and applying the logic 1. on any sub file in `tests/**`
1. based on labels applyied to the PR, if anything outside `tests/` folder is modified.
