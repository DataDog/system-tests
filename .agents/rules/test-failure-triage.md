# Test Failure Triage

> **DRAFT**

Apply this rule when a user asks to triage a failing test (e.g. "triage this failure", "this test failed on the nightly, handle it").
The input is usually a test name, a CI job URL, or a Test Optimization link.

The key question is to determine the root cause. Runs on this CI use the last release of all components (except rust, which runs on its `dev` version). A regression in a component should already have been caught by that component's own CI, which runs system-tests on its dev version. So the root cause is unlikely to be a tested component: look first at system-tests-side causes. The outcome of the process is based on the most probable culprit.

The procedure has six steps. **Never create a ticket or a PR without an explicit confirmation from the user** (see [Confirmation](#confirmation)).

## Possible culprits

* A component has been released, and a test was activated only for the released version of this component, so it was never tested before: a test activated at `>=X.Y.Z` is skipped in the component's CI (`X.Y.Z-dev` < `X.Y.Z` in semver), and runs for the first time once `X.Y.Z` is released
* A test is flaky because something in the test logic is flaky
* A test is flaky because something in a tested component is flaky
* A system-tests change (test, weblog or `utils/`): the usual suspect. Look at `git log` between the system-tests commits of the last pass and the first failure
* A weblog dependency that is not pinned has been updated: the failure starts without any system-tests or component change. Low-hanging fruit: pin the dependency in the weblog
* An agent release: easy to spot, it breaks almost all tracers at once, right after the agent version (`@systest.suite.context.agent`) changes

Not culprits: infrastructure issues do not make a test fail (they break the setup, not the test), and system-tests does not use the real Datadog backend anymore.

## Key Documentation

- [test-activation.md](test-activation.md): How to write the skip (manifest vs decorator)
- [manifest.md](../../docs/edit/manifest.md): Manifest format
- [skip-tests.md](../../docs/edit/skip-tests.md): Declarations and their behavior (`bug`, `flaky`, ...)
- [utils/_features.py](../../utils/_features.py): Features and their owner team

---

## Step 1: Gather recurrence data (Test Optimization)

Use the Datadog MCP test tools (`search_datadog_test_events`, `aggregate_datadog_test_events`).

### Useful attributes

| Attribute | Content |
|-----------|---------|
| `@test.service:system-tests` | Scopes to system-tests results |
| `@test.name` | `tests.<path>.<Class>.<method>[<weblog>]` |
| `@test.status` / `@test.final_status` | `pass`, `fail`, `skip` |
| `@test.codeowners` | Owner team(s), e.g. `@DataDog/asm-libraries` |
| `@systest.suite.context.scenario` | Scenario name |
| `@systest.suite.context.weblog_variant` | Weblog |
| `@systest.suite.context.library.name` / `.version` | Tested library and version |
| `@systest.suite.context.agent` | Agent version |
| `@ci.pipeline.name` / `@ci.pipeline.url` | Pipeline (e.g. `Nightly`) and run URL |
| `@git.branch` / `@git.commit.sha` | system-tests branch and commit |
| `@error.message` | Assertion and stack trace |

Do not rely on the Test Optimization flaky tags (`@test.is_flaky`, `@test.is_known_flaky`, `@test.is_new_flaky`) or on `get_datadog_flaky_tests`. Those are based on a test both passing and failing on the same commit, and system-tests never runs the same test twice on a commit, so they are mostly meaningless here. Assess flakiness from the pass/fail ratio across runs instead (question 2 below).

### Questions to answer

Query at least the last 30 days (`from: now-30d`), on `@git.is_default_branch:true`, then answer:

1. **Since when?** First failure date, and the last passing run before it.
2. **How often?** Fail/pass ratio on the same (test, scenario, weblog, library) combination. A mix of pass and fail on the same versions suggests flakiness; a consistent failure suggests a regression.
3. **Which scope?** Does it fail on one weblog or all of them? One scenario or all of them? One library version or from a given version onwards? Other tests of the same class/feature failing at the same time? This scope is a huge hint to determine the culprit.
4. **What changed?** Note the library version, agent version and system-tests commit of the last pass and of the first failure (they are investigated in step 2).
5. **Same error?** Compare `@error.message` across failures, to tell whether it's one root cause or several.
6. **Already known?** Check system-tests manifests to see if other failures are registered on the same tests.

---

## Step 2: Gather recent changes

Based on the step 1 results, identify the change that introduced the error. Check each [possible culprit](#possible-culprits), starting with the most likely:

- **system-tests changed** between the last pass and the first failure → `git log <last-pass-sha>..<first-fail-sha>` on:
  - `manifests/<library>.yml`: a test activation, in particular one at exactly the newly released version
  - the test file, and the weblog (`utils/build/docker/<library>/`)
  - `utils/`
- **agent version changed** → check whether almost all tracers started failing at the same time. If so, it's the agent
- **library version changed** → look at the tracer repository commits between both versions (`DataDog/dd-trace-<lang>`). Remember that this is unlikely (see above)
- **nothing changed** → either the test is flaky (mix of pass and fail on the same versions), or a weblog dependency that is not pinned has been updated (look at the weblog Dockerfile and dependency files)

## Step 3: Try to propose a fix

If you have enough confidence about the root cause and how we should fix it, propose to the user to create a PR to fix the issue (see [Confirmation](#confirmation)). If the user refuses, go to step 4.

## Step 4: JIRA ticket

### Find the JIRA project

The JIRA project is derived from the owner of the feature tested by the test. Find the `@features.<name>` decorator on the test class, then the `owner=_Owner.<key>` of this feature in `utils/_features.py`. Here is the map owner key -> JIRA project to use:

* agent_apm: APMLP (the agent team does not run system-tests, so the system-tests team will mostly be the first line of defense for agent failures)
* asm: APPSEC
* debugger: DEBUG
* idm: AIDM
* dsm: DSMOM
* sdk_capabilities: APMAPI
* ffe: FFE
* language_platform: APMLP
* injection_platform: INPLAT
* ml_observability: MLOB
* profiler: PROFLIB
* rp: APMSP

If the project can't be determined, ask the user.

### JIRA tools

Create and update tickets yourself, with the Atlassian MCP server (`datadoghq.atlassian.net`):

- `mcp__atlassian__getAccessibleAtlassianResources`: get the `cloudId` required by the other tools, and check the server is connected
- `mcp__atlassian__searchJiraIssuesUsingJql`: search existing tickets
- `mcp__atlassian__createJiraIssue`: create the ticket
- `mcp__atlassian__addCommentToJiraIssue`: add new data, or the skip PR link, to a ticket

If the Atlassian MCP server is not available or not authenticated, stop and tell the user, instead of falling back to another method.

### Avoid duplicates

Before proposing a new ticket, search JIRA for an open ticket mentioning the test class or method name (e.g. JQL `project = <PROJECT> AND statusCategory != Done AND text ~ "<Class>"`). If one exists, propose to reuse it (and add a comment with the new data) instead of creating a new one.

### Ticket content

- **Title:** `[system-tests] <Class>::<method> fails on <library> <scope>`
- **Issue type:** Bug
- **Body:**
  - Test: full test path (`tests/...py::Class::method`)
  - Scope: scenario(s), weblog(s), library version(s), agent version
  - Since: first failure date, last passing run
  - Recurrence: fail/pass counts over the analysed period
  - Suspected cause: what changed between last pass and first failure, and confidence level
  - Error: the relevant part of `@error.message`
  - Links: failing CI run(s), Test Optimization query
  - Link to the system-tests PR that skips the test: the ticket is created before this PR, so add the link as a ticket comment once the PR from step 6 is open
- **Labels:** `system-tests`

---

## Step 5: Ping the team

For now, the system-tests team takes care of this part. Do not ping anyone.

---

## Step 6: Skip PR

Follow [test-activation.md](test-activation.md). In particular:

- Use manifests, except where [test-activation.md](test-activation.md) requires a decorator (e.g. a scenario-specific skip)
- use `bug (<JIRA-KEY>)` for a regression, `flaky (<JIRA-KEY>)` for an intermittent failure. `bug` still runs the test as xfail (a fix is detected as xpass), `flaky` does not run it at all
- scope the skip to what step 1 found: only the failing weblog(s) (`weblog_declaration`), only from the failing version (`component_version`), only the failing method rather than the whole class
- run `./format.sh` after modifying a manifest
- always open the PR as a draft (this also applies to the fix PR from step 3)

---

## Confirmation

After the steps 1–2 analysis (and **before** creating anything), post a summary and wait for an explicit "go" from the user:

```
**Test:** tests/...::Class::method
**Scope:** <scenario> / <weblog(s)> / <library> <versions>
**Since:** <date> (last pass: <date>, <run url>)
**Recurrence:** <n> failures / <m> runs in the last <d> days
**Suspected cause:** <regression in library X.Y.Z | flaky | system-tests change | infra> (<confidence>)

**Proposed actions:**
1. Fix: <PR description> | none
2. JIRA: create in <PROJECT> | reuse <KEY>
3. Skip: `<manifest entry or decorator>` in `<file>`
```

The user may amend any part. Only then create the fix PR, or the ticket and the skip PR.
