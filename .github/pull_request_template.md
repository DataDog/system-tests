## Description

<!-- A brief description of the change being made with this pull request. -->

## Motivation

<!-- What inspired you to submit this pull request? -->

## Workflow

1. ⚠️⚠️ Create your PR as draft
2. Follow the style guidelines of this project (See [how to easily lint the code](https://github.com/DataDog/system-tests/blob/main/docs/edit/lint.md))
3. Work on you PR until the CI passes (if something not related to your task is failing, you can ignore it)
4. Mark it as ready for review

Once your PR is reviewed, you can merge it! :heart:

## Reviewer checklist

* [ ] Check what scenarios are modified. If needed, add the relevant label (`run-parametric-scenario`, `run-profiling-scenario`...). If this PR modifies any system-tests internal, then add the `run-all-scenarios` label ([more info](https://github.com/DataDog/system-tests/blob/main/docs/CI/system-tests-ci.md)). 
* [ ] CI is green
   * [ ] If not, failing jobs are not related to this change (and you are 100% sure about this statement)
* if any of `build-some-image` label is present
  1. is the image labl have been updated ? 
  2. just before merging, locally build and push the image to hub.docker.com
