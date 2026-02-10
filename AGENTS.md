# AGENTS.md - System-Tests

> AI Coding Agent instructions for system-tests repository

## Important: Shared Rules with Cursor

**All AI assistant rules are maintained in the `.cursor/rules/` directory.**

All coding agents MUST read and follow all rules from these files:

## Always Applied Rules

Read and follow these rules in EVERY interaction:

1. **`.cursor/rules/general-behavior.mdc`** - Communication style, documentation references, Slack support
2. **`.cursor/rules/system-tests-overview.mdc`** - Project overview, main concepts, terminology
3. **`.cursor/rules/repository-structure.mdc`** - Repository structure, test class conventions
4. **`.cursor/rules/fine-tuning-guidance.mdc`** - Documentation navigation, scenario discovery
5. **`.cursor/rules/code-format-standards.mdc`** - Code formatting requirements (shellcheck, mypy, YAML)
6. **`.cursor/rules/aws-ssi-testing.mdc`** - AWS SSI testing guidelines
7. **`.cursor/rules/end-to-end-testing.mdc`** - End-to-end testing guidelines
8. **`.cursor/rules/k8s-ssi.mdc`** - Kubernetes library injection testing
9. **`.cursor/rules/test-activation.mdc`** - Test activation/deactivation rules
10. **`.cursor/rules/doc.mdc`** - Rules for editing the documentation

## Manual Rules (Apply Only When Explicitly Requested)

11. **`.cursor/rules/java-endpoint-prompt.mdc`** - Java endpoint creation prompts
12. **`.cursor/rules/promptfoo-llm.mdc`** - Promptfoo LLM testing guidelines

## Pull request review guidelines

13. **`.cursor/rules/pr-review.mdc`** - Pull Request review guidelines and checklist

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

