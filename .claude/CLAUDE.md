# System-Tests - Claude AI Configuration

## Important: Shared Rules with Cursor

**All AI assistant rules are maintained in the `.cursor/rules/` directory.**

## Always Applied Rules

Claude MUST read and follow all rules from these files and follow these rules in EVERY interaction:

1. **`.cursor/rules/general-behavior.mdc`** - AI behaviour: communication style, documentation references, Slack support
2. **`.cursor/rules/system-tests-overview.mdc`** - Project overview, main concepts, terminology
3. **`.cursor/rules/repository-structure.mdc`** - Repository structure, test class conventions
4. **`.cursor/rules/fine-tuning-guidance.mdc`** - Documentation navigation, scenario discovery
5. **`.cursor/rules/code-format-standards.mdc`** - Code formatting requirements (shellcheck, mypy, YAML)
6. **`.cursor/rules/aws-ssi-testing.mdc`** - AWS SSI testing guidelines
7. **`.cursor/rules/end-to-end-testing.mdc`** - End-to-end testing guidelines
8. **`.cursor/rules/k8s-ssi.mdc`** - Kubernetes library injection testing
9. **`.cursor/rules/test-activation.mdc`** - Test activation/deactivation rules

## Manual Rules (Apply Only When Explicitly Requested)

10. **`.cursor/rules/java-endpoint-prompt.mdc`** - Java endpoint creation prompts

---

## Quick Reference

- **Project**: System tests for Datadog tracer libraries (Java, Node.js, Python, PHP, Ruby, C++, .NET, Go, Rust)
- **Framework**: pytest
- **Main Scenarios**: end-to-end, parametric, SSI, Kubernetes
- **Scenario Source**: `utils/_context/_scenarios/__init__.py`
- **Support**: #apm-shared-testing Slack channel

---

**Note**: This `CLAUDE.md` is a pointer to the actual rules. All detailed rules and guidelines are in the `.cursor/rules/*.mdc` files. Read those files directly for complete context.