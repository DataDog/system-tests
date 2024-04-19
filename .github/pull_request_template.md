## Motivation

<!-- What inspired you to submit this pull request? -->

## Changes

<!-- A brief description of the change being made with this pull request. -->

## Workflow


1. ⚠️ Create your PR as draft ⚠️
2. Work on you PR until the CI passes (if something not related to your task is failing, you can ignore it)
3. Mark it as ready for review
    * Test logic is modified? -> Get a review from RFC owner. We're working on refining the `codeowners` file quickly.
    * Framework is modified, or non obvious usage of it -> get a review from [R&P team](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)

:rocket: Once your PR is reviewed, you can merge it!

🛟 [#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X) 🛟

## Reviewer checklist

* [ ] [Relevant label](https://github.com/DataDog/system-tests/blob/main/docs/CI/labels.md) (`run-parametric-scenario`, `run-profiling-scenario`...) are presents
* [ ] If PR title starts with `[<language>]`, double-check that only `<language>` is impacted by the change
* [ ] No system-tests internal is modified. Otherwise, I have the approval from [R&P team](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)
* [ ] CI is green, or failing jobs are not related to this change (and you are 100% sure about this statement)
* [ ] A docker base image is modified?
    * [ ] the relevant `build-XXX-image` label is present
* [ ] A scenario is added (or removed)?
    * [ ] Get a review from [R&P team](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)

