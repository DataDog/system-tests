# GitHub MCP Server Setup for system-tests

This guide explains how to set up GitHub MCP (Model Context Protocol) server integration for use with Cursor IDE in the system-tests repository.

## GitHub MCP Server Setup

The `setup_github_mcp.sh` script automates the process of setting up GitHub MCP server integration for use with Cursor IDE.

### Prerequisites

Before running the setup script, ensure you have:

1. **ddtool** - Datadog CLI tool installed and accessible in your PATH
2. **Docker** - Docker installed and running
3. **Cursor IDE** - Cursor IDE installed (this setup is specifically for Cursor)
4. **sudo access** - Required to create script in `/usr/local/bin/`

### What the script does

The script automates these steps:

1. **Dependency Check**: Verifies that `ddtool` and `docker` are available
2. **GitHub Authentication**: Runs `ddtool auth github login` to authenticate with GitHub
3. **MCP Script Creation**: Creates `/usr/local/bin/start-github-mcp.sh` with the GitHub MCP server startup script
4. **Configuration Update**: Creates or updates `~/.cursor/mcp.json` with the GitHub MCP server configuration
5. **Verification**: Verifies the setup is working correctly

### Usage

```bash
# Navigate to the system-tests repository root
cd /path/to/system-tests

# Run the setup script
./utils/scripts/ai/setup_github_mcp.sh
```

### Manual Steps (Alternative)

If you prefer to set up manually or need to troubleshoot, here are the manual steps:

1. **Authenticate with GitHub**:
   ```bash
   ddtool auth github login
   ```

2. **Create the MCP server script**:
   ```bash
   sudo tee /usr/local/bin/start-github-mcp.sh > /dev/null << 'EOF'
   #!/bin/bash

   generate_github_token() {
     ddtool auth github token
   }

   # Generate the token
   GITHUB_TOKEN=$(generate_github_token)

   # Start the MCP server with the token
   docker run -i --rm \
     -e GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_TOKEN" \
     ghcr.io/github/github-mcp-server
   EOF

   sudo chmod +x /usr/local/bin/start-github-mcp.sh
   ```

3. **Update your Cursor MCP configuration**:
   Add this to your `~/.cursor/mcp.json` file:
   ```json
   {
     "mcpServers": {
       "github_datadog_mcp": {
         "command": "bash",
         "args": [
           "/usr/local/bin/start-github-mcp.sh"
         ],
         "env": {}
       }
     }
   }
   ```

### After Setup

1. **Restart Cursor IDE** to load the new MCP configuration
2. The GitHub MCP server will be available as `github_datadog_mcp`
3. You can now use GitHub-related AI tools in your Cursor IDE

## Example Use Cases

Once the GitHub MCP server is set up, you can use natural language to perform various GitHub operations. Here are some practical examples:

### Repository Analysis Examples

**Track file changes across commits:**
```
Show the latest changes to tests/otel/test_context_propagation.py on main in DataDog/system-tests. For each change include: short SHA, author, date, commit title, related PR # and PR title (if any).
```

**Monitor recent pull requests:**
```
List the 10 most recent PRs merged into main for DataDog/system-tests (number, title, author, merged_at, link).
```

### Cross-Repository Analysis

**Release and PR tracking for related repositories:**
```
In DataDog/dd-trace-java:
1) List the 5 most recent releases with columns: tag, release_name, published_at (ISO 8601), url.
2) List the 5 most recent merged PRs. I would like to know this data for each PR: Pr number, Pr title or short description, Pr author and merged date.
Afterwards, provide a brief summary (3–5 bullets) of notable changes across those releases/PRs.
```

### Other Common Operations

- **Code search**: Find specific functions, classes, or patterns across repositories
- **Issue tracking**: List open issues, search by labels, or track issue progress
- **Branch analysis**: Compare branches, find differences, or track branch status
- **Workflow monitoring**: Check CI/CD status, view workflow runs, or analyze build failures
- **Release management**: Track releases, compare versions, or analyze release notes

### Tips for Best Results

- Be specific about repository names (e.g., `DataDog/system-tests`)
- Include the data you want to see (SHA, author, date, etc.)
- Use natural language - the AI understands context and intent
- Combine multiple requests for comprehensive analysis

### Configuration Files

- **MCP Script**: `/usr/local/bin/start-github-mcp.sh` - The script that starts the GitHub MCP server
- **MCP Config**: `~/.cursor/mcp.json` - Cursor IDE configuration for MCP servers

### Troubleshooting

**Authentication Issues**:
- Ensure you're logged in with `ddtool auth github login`
- Test token generation with `ddtool auth github token`

**Permission Issues**:
- The script requires sudo access to create files in `/usr/local/bin/`
- Ensure your user has sudo privileges

**Docker Issues**:
- Ensure Docker is running: `docker info`
- Test Docker access: `docker run hello-world`

**Cursor Issues**:
- Restart Cursor IDE after configuration changes
- Check the MCP configuration in Cursor's settings
- Verify the `~/.cursor/mcp.json` file syntax

### Support

For questions or issues:
- Check the [system-tests documentation](../README.md)
- Ask in the Slack channel **#apm-shared-testing**
- Open an issue in the system-tests repository

---

**Note**: This setup is specifically designed for users of the system-tests repository who want to integrate GitHub MCP server capabilities with their Cursor IDE for enhanced AI assistance with GitHub operations.