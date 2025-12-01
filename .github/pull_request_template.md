## Motivation

<!-- What inspired you to submit this pull request? -->

## Changes

<!-- A brief description of the change being made with this pull request. -->

## Workflow

1. ⚠️ Create your PR as draft ⚠️
2. Work on you PR until the CI passes
3. Mark it as ready for review
    * Test logic is modified? -> Get a review from RFC owner.
    * Framework is modified, or non obvious usage of it -> get a review from [R&P team](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)

:rocket: Once your PR is reviewed and the CI green, you can merge it!

🛟 [#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X) 🛟

## Reviewer checklist

* [ ] If PR title starts with `[<language>]`, double-check that only `<language>` is impacted by the change
* [ ] No system-tests internal is modified. Otherwise, I have the approval from [R&P team](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)
* [ ] A docker base image is modified?
    * [ ] the relevant `build-XXX-image` label is present
* [ ] A scenario is added (or removed)?
    * [ ] Get a review from [R&P team](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)
