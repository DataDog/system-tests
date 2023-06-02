## Description

<!-- A brief description of the change being made with this pull request. -->

## Motivation

<!-- What inspired you to submit this pull request? -->

## Reviewer checklist

* [ ] If this PR modify anything else than sctriclty the default scenario, then remove the `run-default-scenario` label
* [ ] CI is green
   * [ ] If not, failing jobs are not related to this change (and you are 100% sure about this statement)

## Workflow

1. ⚠️⚠️ Create your PR as draft
2. Follows the style guidelines of this project (See [how to easily lint the code](https://github.com/DataDog/system-tests/blob/main/docs/edit/lint.md))
3. Work on you PR until the CI passes (if something not related to your task is failing, you can ignore it)
4. Mark it as ready for review

> **_NOTE:_**  By default in PR only default scenario tests will be launched. Temove `run-default-scenario` label to run all scenarios ([more info](https://datadoghq.atlassian.net/wiki/spaces/APMINT/pages/2866381467/CI+Workflow+Github+Actions))

Once your PR is reviewed, you can merge it ! :heart:
