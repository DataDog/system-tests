# Target Artifact Staging Spec

## Problem Statement

System-tests currently has two different mechanisms for choosing the target artifact to test.
Development artifact selection is mostly centralized in the legacy binary-loading script, while production artifact selection often happens dynamically inside Dockerfiles or installer scripts. This makes ownership unclear, makes non-library test targets fit awkwardly into library-oriented workflows, and makes Docker layer cache behavior hard to reason about when production releases change.

The user wants each test target to own its target artifact selection logic for both development and production. Artifact staging should happen before the Docker build or test run consumes the selected artifact entries. The Docker build should not dynamically discover the latest production release for the target artifact, because a mutable selector such as `latest` can match every version ever released and does not provide a bounded contract for cache invalidation.

## Solution

Introduce a Python-based artifact staging mechanism where every test target defines two top-level environment classes, one for development and one for production. Both classes implement a common Protocol. Each environment class declares the artifact inputs it needs, then maps resolved artifact inputs to generated artifact entries.

The orchestrator owns side effects: loading local environment configuration, resolving declared artifact inputs through shared resolvers, writing artifact entries, and maintaining the artifact manifest. Target environment classes remain side-effect-free and only return text artifact entries.

Generated artifact entries must represent bounded artifact selectors. They may use version numbers, commit SHAs, release tags, package versions, or image digests. They must not use unbounded rolling selectors such as `latest`. When a provider-specific fetch selector cannot be bounded, the target must also emit a visible selection marker containing the bounded selector used for cache identity.

The legacy binary-loading command remains available as a compatibility wrapper. The canonical behavior becomes target artifact staging, but existing local and CI invocations keep working transparently.

## User Stories

1. As a system-tests user, I want each test target to define its own target artifact selection, so that target-specific behavior is easy to find and review.
2. As a system-tests user, I want development and production target artifact selection to live together, so that both environments follow the same model.
3. As a system-tests user, I want production artifact selection to happen before Docker builds dynamically install a tracer, so that Docker layer cache invalidation is easier to reason about.
4. As a system-tests user, I want production target artifact entries to avoid `latest`, so that a staged artifact selection has a bounded meaning.
5. As a system-tests user, I want version selectors to remain valid when they match multiple architecture-specific payloads, so that runtime-specific installers can still choose the correct artifact.
6. As a system-tests user, I want development branch inputs to resolve to bounded selectors when possible, so that testing a branch still has a stable cache identity.
7. As a system-tests user, I want providers that require branch-based fetching to write an additional selection marker, so that cache invalidation still tracks the resolved commit.
8. As a system-tests user, I want selection markers to be documented clearly, so that I understand when they are required and why.
9. As a system-tests user, I want generated artifact entries to be text files, so that the staging contract stays simple and inspectable.
10. As a system-tests user, I want local payload overrides to remain supported outside generated artifact staging, so that I can still test a local jar, wheel, archive, native library, or checkout.
11. As a system-tests user, I want generated artifact staging to avoid overwriting my manual payload overrides, so that local testing artifacts are not destroyed.
12. As a system-tests user, I want generated artifact staging to avoid overwriting my manual marker files, so that explicit local selections are not silently replaced.
13. As a system-tests user, I want a clear error when a generated artifact entry conflicts with an unowned file, so that I know which local file to remove.
14. As a system-tests user, I want generated artifact entries from previous runs to be refreshed safely, so that stale generated files do not keep affecting builds.
15. As a system-tests user, I want staging one environment for a target to replace the previous environment for that same target, so that development and production selections cannot be active for the same target at the same time.
16. As a system-tests user, I want staging one test target to leave other staged targets alone, so that dependency artifacts and multi-target workflows can coexist.
17. As a system-tests user, I want artifact staging to track generated ownership in a manifest, so that the orchestrator can distinguish generated files from manual files.
18. As a system-tests user, I want the artifact manifest to avoid duplicating artifact entry contents, so that the actual staged files remain the source of truth.
19. As a system-tests user, I want structured artifact entries to use JSON, so that multi-field references are not encoded with fragile delimiters.
20. As a system-tests user, I want JSON artifact entries to use a JSON file extension, so that format expectations are obvious.
21. As a target maintainer, I want my target's artifact inputs to be explicitly declared, so that repo names, defaults, and external providers are not hidden in orchestration code.
22. As a target maintainer, I want shared resolvers for common external metadata lookups, so that target files do not duplicate GitHub, registry, or environment parsing logic.
23. As a target maintainer, I want target environment classes to receive resolved inputs, so that I can unit test target mapping without network, filesystem, or environment side effects.
24. As a target maintainer, I want the target module to own ecosystem-specific selection semantics, so that Java, Go, PHP, C, Lambda, and native-web-server targets can express their different needs.
25. As a target maintainer, I want authenticated artifact entries to contain only non-secret metadata, so that uploaded artifact bundles do not leak credentials.
26. As a CI maintainer, I want GitLab build jobs to run artifact staging directly, so that small workloads do not pay the startup cost of a separate staging job.
27. As a CI maintainer, I want GitLab parametric jobs to run artifact staging directly, so that parametric runs have target artifacts even when no weblog build job exists.
28. As a CI maintainer, I want GitLab custom runs with upstream artifact bundles to skip artifact staging, so that external artifacts remain the source of truth.
29. As a CI maintainer, I want the staging command to accept custom as a no-op, so that templates can call a single command shape safely.
30. As a CI maintainer, I want GitHub workflows to keep working transparently during migration, so that the refactor does not require immediate GitHub production-flow changes.
31. As a CI maintainer, I want the legacy command name to keep working, so that existing workflows and local habits do not break during migration.
32. As a system-tests maintainer, I want every test target to define real development and production staging behavior, so that there are no placeholder loaders.
33. As a system-tests maintainer, I want dependency artifacts such as the agent to stay outside the test target protocol, so that test targets and dependencies remain separate domain concepts.
34. As a system-tests maintainer, I want WAF rule set loading to remain outside the test target protocol, so that overlay artifacts do not blur target ownership.
35. As a system-tests maintainer, I want the target artifact context to stay target-level, so that one staged artifact bundle can be reused across many weblog variants.
36. As a system-tests maintainer, I want architecture and runtime-specific payload selection to remain in installers when needed, so that the artifact staging phase does not need weblog-specific facts.
37. As a system-tests maintainer, I want remote lookups to fetch as little data as possible, so that staging resolves metadata or bounded references without downloading payloads unnecessarily.
38. As a system-tests maintainer, I want GitHub Actions artifact staging to return metadata rather than payloads, so that Docker builds fetch the selected artifact only once.
39. As a system-tests maintainer, I want OCI production image selectors to resolve to digests, so that image-based target artifacts do not use mutable tags.
40. As a system-tests maintainer, I want the bounded-selector rule documented as a contract rather than enforced by expensive runtime checks, so that the system remains practical.

## Implementation Decisions

- The canonical operation is artifact staging, not binary loading. The legacy command remains as a compatibility entrypoint.
- Every test target must provide real development and production artifact staging behavior. Checked-in placeholder behavior is not acceptable.
- A test target is the component selected as the CI matrix library value. Dependencies and overlays are not test targets.
- Dependency artifacts, including the agent, remain compatibility-only behavior in the orchestrator and are outside the per-test-target Protocol.
- WAF rule set loading remains compatibility-only behavior in the orchestrator and is outside the per-test-target Protocol.
- Each test target owns a target artifact module in its existing target-specific Docker area.
- Shared protocol, models, resolvers, and orchestration live in a normal importable Python package outside the Docker build asset tree.
- The orchestrator imports each target artifact module dynamically by file location instead of turning every Docker target directory into a Python package.
- Each target artifact module exposes two top-level classes, `Dev` and `Prod`.
- `Dev` and `Prod` explicitly inherit from the shared Protocol type supplied by the typing module.
- `Dev` and `Prod` have no constructor arguments. Runtime data is passed through context and resolved artifact inputs.
- The Protocol exposes one method for declaring artifact inputs and one method for returning artifact entries.
- Artifact input declarations are explicit for both development and production. The orchestrator does not infer repository names, default branches, production release sources, or ecosystem semantics.
- Resolved artifact inputs are accessed as a mapping keyed by input name.
- Resolved artifact input values are typed frozen dataclasses, not plain strings.
- Target artifact functions are side-effect-free. They do not read environment variables, read or write files, call subprocesses, or perform network requests.
- The orchestrator owns side effects: environment loading, remote metadata resolution, artifact entry writing, and manifest maintenance.
- Generated artifact entries are text-only. Payload bytes and local checkouts remain manual payload overrides outside this loader protocol.
- Single-value artifact entries use plain text.
- Multi-field artifact entries use JSON and their filenames indicate the JSON format.
- Artifact entries must use bounded artifact selectors by contract. The shared implementation should document this rule but should not try to prove arbitrary content is valid.
- Mutable development inputs such as branch names should resolve to bounded selectors before artifact entries are generated when the provider supports that.
- When a provider requires an unbounded or provider-specific fetch selector, the loader must also emit a selection marker that contains the bounded selector used for artifact selection identity.
- Selection markers are visible, documented artifact entries. They are required when the installer-facing entry cannot itself be bounded.
- A shared helper creates provider-fetch entries with the required selection marker, reducing the chance that a target forgets it.
- Production OCI image references resolve to digests.
- GitHub latest release inputs return minimal release metadata by default. Asset metadata is included only when a target requests it.
- GitHub Actions artifact inputs resolve to stable artifact metadata, not downloaded payloads.
- Artifact entries that require authenticated downloads contain only non-secret metadata. Credentials are supplied separately by the build environment.
- The command loads local environment configuration by default using the Python dotenv package. Process environment variables override dotenv values.
- The `custom` environment is an orchestrator-only no-op. It is not represented in target modules.
- The artifact manifest is a single generated manifest for all staged targets in the staging directory.
- The manifest stores versioned ownership metadata and content hashes, not duplicate artifact entry contents.
- The manifest forbids two owners from owning the same artifact entry filename.
- Staging a target in one environment removes previously owned entries for other environments of the same target.
- Staging a target does not remove generated entries owned by other targets.
- Staging removes stale previously owned entries for the same target when the new run no longer emits them.
- Staging refuses to overwrite unowned existing files. There is no force mode in the first implementation.
- There is no clean subcommand in the first implementation.
- GitHub integration is kept transparent for now. Existing development artifact preparation continues through the compatibility command, and new production outputs are ignored until GitHub workflows choose to consume them.
- GitLab generated build jobs run artifact staging directly using the job's CI environment.
- GitLab generated parametric jobs run artifact staging directly using the job's CI environment.
- GitLab custom jobs with upstream artifact bundles skip artifact staging because the upstream bundle is the selected artifact source of truth.
- GitLab accepts the small risk that per-job production resolution could differ if a release changes mid-pipeline. This race is considered extremely unlikely and preferable to adding job startup overhead.

## Testing Decisions

- The main test seam is the artifact staging CLI/orchestrator. Tests should execute the staging flow at the command boundary with fake or stubbed resolvers and inspect the staged artifact entries plus manifest behavior.
- Target environment classes should be tested through their public Protocol methods by passing fake resolved inputs and asserting returned artifact entries. Tests should not inspect target implementation internals.
- Manifest behavior should be tested through observable filesystem effects: safe overwrite of owned files, refusal to overwrite unowned files, cleanup of stale owned entries, replacement of a target's previous environment, preservation of other targets, and owner conflict failures.
- GitLab integration should be tested through the existing pipeline rendering seam. Generated jobs should include artifact staging in build and parametric jobs, skip it for custom upstream artifact bundles, and avoid adding a separate staging job.
- Compatibility behavior should be tested through the legacy command entrypoint, showing that existing invocations continue to route to the new staging behavior.
- Custom environment behavior should be tested at the CLI/orchestrator seam as a successful no-op that does not load target modules or write manifest changes.
- Expected user/configuration failures should raise the shared domain exception and produce clear CLI errors.
- Tests should not perform real network calls. GitHub release metadata, GitHub Actions artifact metadata, branch-to-SHA resolution, and OCI digest resolution should be exercised through resolver fakes.
- Tests should not assert private helper call sequences when the same behavior can be verified through generated artifact entries, manifest contents, and rendered CI commands.
- Prior art exists in current tests for the legacy binary-loading command and GitLab pipeline rendering. The new tests should reuse those high-level seams where possible rather than spreading assertions across many low-level helpers.

## Out of Scope

- Publishing this spec to an issue tracker.
- Adding GitHub production artifact staging to workflows immediately.
- Adding runtime purity enforcement, monkeypatch-based side-effect tests, or AST guards.
- Adding a force option.
- Adding a clean subcommand.
- Turning dependency artifacts into test target loaders.
- Turning WAF rule set loading into a test target loader.
- Generating payload artifact entries.
- Removing support for manual payload overrides.
- Making the target artifact context weblog-specific, runtime-specific, or architecture-specific.
- Proving bounded-selector validity for arbitrary strings at runtime.
- Adding broad generic downloader abstractions before a target needs them.

## Further Notes

- All test targets currently have a matching target-specific Docker directory. Extra Docker directories such as shared support, dependency, and proxy directories are not test targets.
- The current C target is a real test target even though it is exercised through GitLab rather than GitHub.
- The agent is a dependency artifact, not a test target.
- The accepted GitLab consistency tradeoff is deliberate: per-job staging may theoretically resolve different production selectors if a release changes mid-pipeline, but the risk is very low and avoids disproportionate job startup cost.
- Documentation should make selection markers highly visible because missing them breaks the cache identity contract when the installer-facing selector is not bounded.
- Teams can ask questions about system-tests behavior in `#apm-shared-testing`.

## Maintainer Checklist

When adding or changing a target's artifact staging behavior:

1. Add or update `utils/build/docker/<target>/artifact.py`.
2. Define top-level `Dev` and `Prod` classes that implement `TargetArtifactEnvironment`.
3. Keep both classes side-effect-free: declare `ArtifactInput` values in `artifact_inputs`, and turn resolved values into text or JSON `ArtifactEntry` values in `artifact_entries`.
4. Put provider lookups in shared resolvers instead of target modules.
5. Emit bounded artifact selectors whenever possible. If an installer-facing entry must use a provider-specific fetch selector, emit a selection marker with `provider_fetch_entries`.
6. Keep local payload override handling in the installer script. Staging should write selectors and metadata, not jar, wheel, zip, tarball, or checkout payloads.
7. Use JSON entries for multi-field references, and give those files a `.json` extension.
8. Add or update `TEST_THE_TEST` coverage that exercises the target through the public Protocol methods with fake resolved inputs.
