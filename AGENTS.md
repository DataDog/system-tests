# AGENTS.md - System-Tests

> AI Coding Agent instructions for system-tests repository

## Important: Shared Rules with Cursor

**All AI assistant rules are maintained in the `.cursor/rules/` directory.**

All coding agents MUST read and follow all rules from these files:

## Always Applied Rules

These rules apply in EVERY interaction. The `@`-imports below inline each file at
session start so the rules are loaded automatically (Cursor reads them via its own
`alwaysApply: true` frontmatter).

- @.cursor/rules/general-behavior.mdc — Communication style, documentation references, Slack support
- @.cursor/rules/system-tests-overview.mdc — Project overview, main concepts, terminology
- @.cursor/rules/repository-structure.mdc — Repository structure, test class conventions
- @.cursor/rules/fine-tuning-guidance.mdc — Documentation navigation, scenario discovery
- @.cursor/rules/code-format-standards.mdc — Code formatting requirements (shellcheck, mypy, YAML)
- @.cursor/rules/aws-ssi-testing.mdc — AWS SSI testing guidelines
- @.cursor/rules/end-to-end-testing.mdc — End-to-end testing guidelines
- @.cursor/rules/parametric-testing.mdc — Parametric scenario testing; use `--skip-parametric-build` when re-running parametric tests without image changes
- @.cursor/rules/k8s-ssi.mdc — Kubernetes library injection testing
- @.cursor/rules/test-activation.mdc — Test activation/deactivation rules
- @.cursor/rules/doc.mdc — Rules for editing the documentation
- @.cursor/rules/devtools.mdc — Developer tools: MCP, GitHub (gh), GitLab (glab) usage

## Manual Rules (Apply Only When Explicitly Requested)

13. **`.cursor/rules/java-endpoint-prompt.mdc`** - Java endpoint creation prompts
14. **`.cursor/rules/promptfoo-llm.mdc`** - Promptfoo LLM testing guidelines

## Pull request review guidelines

15. **`.cursor/rules/pr-review.mdc`** - Pull Request review guidelines and checklist

---

## Quick Reference

- **Project**: System tests for Datadog tracer libraries (Java, Node.js, Python, PHP, Ruby, C++, .NET, Go, Rust)
- **Framework**: pytest
- **Main Scenarios**: end-to-end, parametric, SSI, Kubernetes
- **Scenario Source**: `utils/_context/_scenarios/__init__.py` (authoritative)
- **Main Documentation**: `README.md` and `docs/` directory
- **Support**: #apm-shared-testing Slack channel

---

**Note**: This `AGENTS.md` is a pointer to the actual rules. All detailed rules and guidelines are in the `.cursor/rules/*.mdc` files. Read those files directly for complete context and instructions.

