# AI Tools Integration Guide

## Table of Contents

- [Overview](#overview)
- [The AI tools](#the-ai-tools)
  - [Github Copilot support](#github-copilot-support)
  - [Cursor](#cursor)
    - [Complete Cursor AI Documentation Suite](#-complete-cursor-ai-documentation-suite)
  - [MCP Servers Integration (Beta)](#mcp-servers-integration-beta)
  - [Claude CLI](#claude-cli)
    - [Configuration Files](#configuration-files)
    - [Setting up Claude CLI](#setting-up-claude-cli)
    - [Running Promptfoo Evaluations](#running-promptfoo-evaluations)
  - [GitHub CLI (gh)](#github-cli-gh)
  - [GitLab CLI (glab)](#gitlab-cli-glab)
  - [Supported AI Tools via AGENTS.md](#supported-ai-tools-via-agentsmd)

## Overview

The `system-tests` repository includes built-in AI integration capabilities designed to enhance developer productivity when implementing new tests, troubleshooting issues, and working with complex testing scenarios. These tools leverage comprehensive context about the repository structure, testing patterns, and best practices to provide intelligent assistance.

Knowledge of AI tools is drawn from the project's documentation (found in the docs directory), the source code itself, and predefined rules and instructions (.cursor/rules). Users are strongly encouraged to actively participate in continuous improvement efforts and contribute new capabilities to enhance the AI tools' functionality and effectiveness.

The default and recommended AI tool for developing with system-tests is Cursor AI. Additionally, **Claude CLI** and other AI coding agents are fully supported through dedicated configuration files. Using alternative tools is encouraged.

## The AI tools

### Github Copilot support

The predefined rules within the `system-tests` repository are optimized specifically for **Cursor AI**, but you can effortlessly adapt them for **GitHub Copilot** using Copilot itself.

To adapt rules for GitHub Copilot:

1. Activate Copilot's **Agent Mode**.
2. Open the Copilot chat and input the following instruction:

   ```
   Parse all files within the .cursor/rules directory, combine their contents into a single new file at .github/copilot-instructions.md, and remove any occurrences of the text:
    ---
    description:
    globs:
    alwaysApply:
    ---
   ```

**Important Reminders:**

* Do not commit the `.github/copilot-instructions.md` file.
* To add new rules or instructions, always use Cursor AI’s standard rule files located at ".cursor/rules"
* If you introduce new instructions or modify existing documentation, always include new tests. These tests are essential for validating the impact and effectiveness of your changes on the AI assistant’s functionality. Please refer to section [Prompt validation](ai-tools-prompt-validation.md) to know about the ai prompt validations.

### Cursor

Cursor AI is the default IDE and automatically integrates the predefined rules located in the .cursor/rules directory. No additional setup is required—the rules will load automatically.

Cursor allows you to add specialized rules tailored for very specific tasks. These rules aren't loaded by default into the AI context but can easily be activated by mentioning them explicitly in the chat, enabling precise and focused interactions.

Visit [Cursor specialized tasks](cursor-specialized-prompts.md) to explore the specialized tasks supported by system-tests. Feel free to create and contribute as many specialized rules as you need—your teammates will greatly appreciate your efforts!

If you introduce new instructions, enhance existing documentation, or improve the predefined rules, you're strongly encouraged to add corresponding tests. These tests play a vital role in validating your enhancements and ensuring the AI assistant performs optimally. For further guidance, see section [Prompt validation](ai-tools-prompt-validation.md).

#### 📚 Complete Cursor AI Documentation Suite

Cursor AI documentation suite:

- **[Cursor AI Comprehensive Guide](cursor-ai-comprehensive-guide.md)**: Complete overview of AI integration with practical examples and workflows
- **[Cursor Practical Examples](cursor-practical-examples.md)**: Real-world examples and step-by-step workflows
- **[Cursor Specialized Prompts](cursor-specialized-prompts.md)**: Manual rule activation guide
- **[AI Tools Prompt Validation (beta)](ai-tools-prompt-validation.md)**: Testing and validation framework

**📖 New to AI in system-tests?** Start with the [Cursor AI Comprehensive Guide](cursor-ai-comprehensive-guide.md) for a complete introduction.

### MCP Servers Integration (Beta)

Model Context Protocol (MCP) servers extend AI capabilities with specialized tools and integrations. The system-tests repository provides several MCP server configurations to enhance your development workflow. MCP servers can be used with any compatible AI tool, including Cursor and Claude CLI.

**Available MCP Servers:**

- **Datadog MCP Server**: Provides CI Visibility integration including pipeline event search and aggregation, test event analysis, flaky test detection, code coverage summaries, and PR insights. Pre-configured in the repository via `.cursor/mcp.json` (for Cursor) and `.mcp.json` (for Claude CLI and other compatible tools). See [Datadog MCP Server Setup](datadog-mcp-server.md) for detailed setup and usage instructions.

To set up MCP servers, follow the specific setup guides for each server. All MCP servers integrate seamlessly with compatible AI tools, providing enhanced context and capabilities for working with the system-tests repository.

### Claude CLI

The system-tests repository provides native support for **Claude CLI** (Anthropic's command-line interface for Claude) through a dedicated configuration in the `.claude/` directory.

#### Configuration Files

```
.claude/
├── CLAUDE.md           # Claude-specific instructions and rules pointer
├── settings.json       # Claude CLI settings (permissions, environment, MCP enablement)
└── settings.local.json # Local settings (personal overrides, not committed)

.mcp.json               # MCP server configuration (shared across AI tools)
```

* **`.claude/CLAUDE.md`**: Contains Claude-specific instructions and points to the shared rules in `.cursor/rules/`
* **`.claude/settings.json`**: Configures Claude CLI behavior, including default permission mode, environment variables, MCP server enablement (e.g., the Datadog MCP server), and the [`DataDog/claude-marketplace`](https://github.com/DataDog/claude-marketplace) plugins which provide Datadog-specific `dd:*` skills (CI debugging, PR feedback, Jira automation, and more)
* **`.claude/settings.local.json`**: Personal overrides for local development (not shared via git)
* **`.mcp.json`**: Defines MCP server connections at the repository root. Claude CLI automatically discovers this file and makes the configured servers available. Currently includes the Datadog MCP server for CI Visibility integration

#### Setting up Claude CLI

1. **Install Claude CLI** following the [official Anthropic documentation](https://docs.anthropic.com/en/docs/claude-code/overview)

2. **Run Claude from the repository root**:

   ```bash
   cd system-tests
   claude
   ```

   Claude CLI automatically reads the `.claude/CLAUDE.md` file and follows the shared rules defined in `.cursor/rules/`.

3. **For non-interactive usage** (e.g., scripts or automation):

   ```bash
   claude --permission-mode acceptEdits -p "Your prompt here"
   ```

#### Running Promptfoo Evaluations

Use the interactive wizard script to run prompt evaluations:

```bash
./utils/scripts/ai/promptfoo_eval.sh
```

The wizard guides you through:
1. Selecting the AI provider (e.g., Claude AI Agent SDK)
2. Choosing which test scenarios to run
3. Automatically executing the evaluation

See [Prompt validation](ai-tools-prompt-validation.md) for more details on the evaluation process.

### GitHub CLI (gh)

The AI tools are configured to use the **GitHub CLI** (`gh`) for all interactions with GitHub (github.com), including repository management, pull requests, issues, and CI/CD operations. The AI assistant will automatically use `gh` commands when performing GitHub-related tasks.

#### Installation

```bash
brew install gh
```

#### Authentication

```bash
gh auth login
```

To verify your authentication status:

```bash
gh auth status
```

### GitLab CLI (glab)

The AI tools are configured to use the **GitLab CLI** (`glab`) for all interactions with GitLab (gitlab.ddbuild.io), including pipeline management, merge requests, and CI/CD operations. The AI assistant will automatically use `glab` commands when performing GitLab-related tasks.

#### Installation

```bash
brew install glab
```

#### Authentication

You will need a **personal access token** to authenticate with GitLab. You can create one from your GitLab profile at **Settings > Access Tokens** on `gitlab.ddbuild.io`.

Once you have your token, authenticate:

```bash
glab auth login --hostname gitlab.ddbuild.io
```

To set the default host:

```bash
glab config set host gitlab.ddbuild.io
```

### Supported AI Tools via AGENTS.md

For compatibility with other AI coding agents (such as Aider, Windsurf, Cline, etc.), the repository includes an `AGENTS.md` file at the root level.

The `AGENTS.md` file serves as a **unified entry point for AI coding agents** that follow the AGENTS.md convention. It:

* Points to the shared rules in `.cursor/rules/` directory
* Lists all "always applied" rules that agents must follow
* Identifies "manual" rules that require explicit activation
* Provides a quick reference for project context

This approach ensures **consistent behavior across all AI tools** by maintaining a single source of truth for rules and instructions.

Any AI coding tool that reads `AGENTS.md` files can benefit from the system-tests configuration, including:

* **Aider** - AI pair programming in your terminal
* **Windsurf** - AI-powered IDE
* **Cline** - Autonomous coding agent for VS Code
* Other tools following the AGENTS.md convention

