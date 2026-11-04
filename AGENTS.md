# AGENTS.md - System-Tests

> AI Coding Agent instructions for system-tests repository

## Shared Agent Rules

**All AI assistant rules are maintained in the `.agents/rules/` directory.**

All coding agents MUST:

1. Read and follow every always-applied rule before starting work.
2. Read the relevant task-specific rules when the request matches their scope.
3. Treat the linked rule files as authoritative; the summaries below do not replace them.

## Always Applied Rules

These rules apply in EVERY interaction.

- [General behavior](.agents/rules/general-behavior.md) — Communication style, documentation references, Slack support
- [System-tests overview](.agents/rules/system-tests-overview.md) — Project overview, main concepts, terminology
- [Repository structure](.agents/rules/repository-structure.md) — Repository structure, test class conventions
- [General guidance](.agents/rules/fine-tuning-guidance.md) — Documentation navigation, scenario discovery
- [Code format standards](.agents/rules/code-format-standards.md) — Shellcheck, mypy, Python, and YAML requirements
- [AWS SSI testing](.agents/rules/aws-ssi-testing.md) — AWS SSI testing guidelines
- [End-to-end testing](.agents/rules/end-to-end-testing.md) — End-to-end testing guidelines
- [Parametric testing](.agents/rules/parametric-testing.md) — Parametric testing and faster iterative runs
- [Kubernetes SSI](.agents/rules/k8s-ssi.md) — Kubernetes library injection testing
- [Test activation](.agents/rules/test-activation.md) — Test activation and deactivation
- [Documentation](.agents/rules/doc.md) — Documentation editing rules
- [Developer tools](.agents/rules/devtools.md) — MCP, GitHub (`gh`), and GitLab (`glab`) usage
- [Official workflows](.agents/rules/tag-official-workflows.md) — CI workflow tagging requirements
- [Test-the-test](.agents/rules/test_the_test.md) — Scenario requirements for `tests/test_the_test`

## Manual Rules (Apply Only When Explicitly Requested)

- [Java endpoint generation](.agents/rules/java-endpoint-prompt.md) — Java endpoint creation workflow
- [Promptfoo evaluations](.agents/rules/promptfoo-llm.md) — Promptfoo LLM testing guidelines

## Pull request review guidelines

- [Pull request review](.agents/rules/pr-review.md) — Apply when reviewing a pull request

---

## Quick Reference

- **Project**: System tests for Datadog tracer libraries (Java, Node.js, Python, PHP, Ruby, C++, .NET, Go, Rust)
- **Framework**: pytest
- **Main Scenarios**: end-to-end, parametric, SSI, Kubernetes
- **Scenario Source**: `utils/_context/_scenarios/__init__.py` lists every scenario (authoritative); each one is defined in a module of `utils/_context/_scenarios/`
- **Main Documentation**: `README.md` and `docs/` directory
- **Support**: #apm-shared-testing Slack channel

---

**Note**: This `AGENTS.md` is a pointer to the actual rules. Read the linked files under `.agents/rules/` directly for complete context and instructions. Reusable agent skills belong under `.agents/skills/`.
