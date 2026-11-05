# Cursor AI and System-Tests: Comprehensive Integration Guide

## Overview

The AI instructions in `system-tests` use the portable [`AGENTS.md`](../../AGENTS.md) convention. Cursor loads the root `AGENTS.md` automatically; that file routes the agent to the authoritative Markdown rules under `.agents/rules/`.

## Agent instruction structure

```text
system-tests/
├── AGENTS.md              # Portable entry point and rule index
├── CLAUDE.md              # Claude Code adapter
├── .agents/
│   ├── rules/             # Authoritative shared rules
│   └── skills/            # Reusable Agent Skills
└── .cursor/
    └── mcp.json           # Cursor-specific MCP configuration
```

`AGENTS.md` separates rules into:

- **Always-applied rules**: every coding agent must read these before starting work.
- **Manual rules**: read only when the user explicitly requests the corresponding workflow.
- **Task-specific rules**: read when the request matches their scope, such as pull request review.

The index in `AGENTS.md` is authoritative for classification. Rule files do not contain Cursor-specific `alwaysApply` or `globs` metadata.

## How Cursor loads the rules

Cursor automatically includes `AGENTS.md` in a new Agent conversation. Linked files are not inlined automatically: the instructions in `AGENTS.md` require Cursor to read the applicable files from `.agents/rules/` with its repository tools.

Start a new conversation after changing `AGENTS.md` or moving rule files so the instruction context is rebuilt.

## Specialized rules

The Java endpoint workflow is stored at `.agents/rules/java-endpoint-prompt.md`. Ask Cursor to apply that rule explicitly when implementing Java weblog endpoints.

Reusable workflows that adopt the open Agent Skills format belong in `.agents/skills/<skill-name>/SKILL.md`.

## Adding a rule

1. Add a standard Markdown file under `.agents/rules/`.
2. Register it in the appropriate section of `AGENTS.md`.
3. Use repository-relative Markdown links.
4. Add or update prompt validation coverage.
5. Start a new Cursor conversation and verify that the agent reads the file.

See [Cursor AI Practical Examples](cursor-practical-examples.md) and [Prompt validation](ai-tools-prompt-validation.md).

