# Datadog MCP Server Setup for system-tests

The Datadog MCP server connects Cursor's AI assistant to Datadog's CI Visibility platform, letting you query pipeline events, test results, flaky tests, code coverage, and PR insights directly from the chat.

## Setup

### 1. Repository Configuration (Pre-configured)

The repository already includes the MCP server configuration in `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "datadog": {
      "url": "https://mcp.datadoghq.com/api/unstable/mcp-server/mcp?toolsets=software-delivery",
      "headers": {}
    }
  }
}
```

### 2. Authentication via SSO

The Datadog MCP server uses SSO for authentication. No API or App keys are required.

1. Open Cursor IDE in the system-tests repository
2. Go to the MCP settings panel and trigger the **login** command on the `datadog` server
   For the in terminal agent use `/mcp login`.
3. A browser tab opens automatically for Datadog SSO login
4. Complete the login in your browser — Cursor picks up the session automatically

After logging in, the MCP tools are immediately available in the AI chat.

## Available Tools

The repository configuration enables the **software-delivery** toolset. See the [official Datadog MCP toolsets documentation](https://docs.datadoghq.com/bits_ai/mcp_server/#toolsets:~:text=MCP%20Server.-,Toolsets,-The%20Datadog%20MCP) for the full list of available tools.

## Example Prompts

```
Show me the latest failed CI jobs on the main branch of DataDog/system-tests
```

```
Find the top 10 flaky tests in system-tests sorted by failure rate
```

```
What issues are blocking PR #1234 in DataDog/system-tests?
```

```
What's the P95 pipeline duration for system-tests over the last 30 days?
```

## Troubleshooting

- **MCP server not available**: Verify `.cursor/mcp.json` exists at the repo root, then restart Cursor
- **Authentication errors**: Re-trigger the login command from the MCP settings panel
- **No data returned**: Ensure CI Visibility is enabled for the target repository in Datadog

For help, ask in **#apm-shared-testing** or consult the [Datadog MCP server docs](https://docs.datadoghq.com/bits_ai/mcp_server/setup/).
