#!/bin/bash

# setup_github_mcp.sh - Setup GitHub MCP Server for system-tests users
# This script automates the process of adding GitHub MCP server integration

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Script configuration
readonly SCRIPT_PATH="/usr/local/bin/start-github-mcp.sh"
readonly MCP_JSON_PATH="$HOME/.cursor/mcp.json"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_dependencies() {
    log_info "Checking dependencies..."

    if ! command -v ddtool &> /dev/null; then
        log_error "ddtool is not installed or not in PATH"
        log_error "Please install ddtool first and try again"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        log_error "Please install Docker first and try again"
        exit 1
    fi

    log_success "All dependencies are available"
}

authenticate_github() {
    log_info "Authenticating with GitHub using ddtool..."

    if ! ddtool auth github login; then
        log_error "Failed to authenticate with GitHub"
        log_error "Please check your credentials and try again"
        exit 1
    fi

    log_success "GitHub authentication completed"
}

create_mcp_script() {
    log_info "Creating GitHub MCP server script at $SCRIPT_PATH..."

    # Check if we have write permissions to /usr/local/bin
    if [[ ! -w "/usr/local/bin" ]]; then
        log_warning "No write permission to /usr/local/bin, using sudo..."
        if ! sudo -v; then
            log_error "sudo access required to create script in /usr/local/bin"
            exit 1
        fi
    fi

    # Create the script content
    local script_content
    script_content=$(cat << 'EOF'
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
)

    # Write the script
    if [[ -w "/usr/local/bin" ]]; then
        echo "$script_content" > "$SCRIPT_PATH"
    else
        echo "$script_content" | sudo tee "$SCRIPT_PATH" > /dev/null
    fi

    # Make it executable
    if [[ -w "/usr/local/bin" ]]; then
        chmod +x "$SCRIPT_PATH"
    else
        sudo chmod +x "$SCRIPT_PATH"
    fi

    log_success "GitHub MCP server script created successfully"
}

create_or_update_mcp_json() {
    log_info "Creating or updating mcp.json configuration..."

    # Create .cursor directory if it doesn't exist
    local cursor_dir
    cursor_dir=$(dirname "$MCP_JSON_PATH")
    if [[ ! -d "$cursor_dir" ]]; then
        mkdir -p "$cursor_dir"
        log_info "Created directory: $cursor_dir"
    fi

    # GitHub MCP server configuration
    local github_mcp_config='{
  "mcpServers": {
    "github_datadog_mcp": {
      "command": "bash",
      "args": [
        "/usr/local/bin/start-github-mcp.sh"
      ],
      "env": {}
    }
  }
}'

    if [[ -f "$MCP_JSON_PATH" ]]; then
        log_info "Existing mcp.json found, backing up..."
        cp "$MCP_JSON_PATH" "${MCP_JSON_PATH}.backup.$(date +%Y%m%d_%H%M%S)"

        # Check if the configuration already exists
        if grep -q "github_datadog_mcp" "$MCP_JSON_PATH"; then
            log_warning "GitHub MCP server configuration already exists in mcp.json"
            read -p "Do you want to overwrite it? (y/N): " -r overwrite
            if [[ ! $overwrite =~ ^[Yy]$ ]]; then
                log_info "Skipping mcp.json update"
                return 0
            fi
        fi

        # Use jq to merge configurations if available, otherwise replace
        if command -v jq &> /dev/null; then
            local temp_file
            temp_file=$(mktemp)
            jq --argjson new_config "$github_mcp_config" \
               '.mcpServers.github_datadog_mcp = $new_config.mcpServers.github_datadog_mcp' \
               "$MCP_JSON_PATH" > "$temp_file" && mv "$temp_file" "$MCP_JSON_PATH"
        else
            log_warning "jq not available, will create new mcp.json file"
            echo "$github_mcp_config" > "$MCP_JSON_PATH"
        fi
    else
        log_info "Creating new mcp.json file..."
        echo "$github_mcp_config" > "$MCP_JSON_PATH"
    fi

    log_success "mcp.json configuration updated successfully"
}

verify_setup() {
    log_info "Verifying setup..."

    # Check if script exists and is executable
    if [[ ! -f "$SCRIPT_PATH" ]]; then
        log_error "GitHub MCP script not found at $SCRIPT_PATH"
        return 1
    fi

    if [[ ! -x "$SCRIPT_PATH" ]]; then
        log_error "GitHub MCP script is not executable"
        return 1
    fi

    # Check if mcp.json exists
    if [[ ! -f "$MCP_JSON_PATH" ]]; then
        log_error "mcp.json not found at $MCP_JSON_PATH"
        return 1
    fi

    # Test if we can generate a token
    log_info "Testing GitHub token generation..."
    if ! ddtool auth github token &> /dev/null; then
        log_warning "Unable to generate GitHub token. Please ensure you're authenticated."
        return 1
    fi

    log_success "Setup verification completed successfully"
    return 0
}

main() {
    echo -e "${BLUE}=== GitHub MCP Server Setup for system-tests ===${NC}"
    echo

    # Check dependencies
    check_dependencies

    # Authenticate with GitHub
    authenticate_github

    # Create MCP script
    create_mcp_script

    # Create or update mcp.json
    create_or_update_mcp_json

    # Verify setup
    if verify_setup; then
        echo
        log_success "GitHub MCP server setup completed successfully!"
        echo
        log_info "Next steps:"
        echo "  1. Restart your Cursor IDE to load the new MCP configuration"
        echo "  2. The GitHub MCP server will be available as 'github_datadog_mcp'"
        echo "  3. You can now use GitHub-related AI tools in your Cursor IDE"
        echo
        log_info "Configuration files:"
        echo "  - MCP Script: $SCRIPT_PATH"
        echo "  - MCP Config: $MCP_JSON_PATH"
    else
        log_error "Setup verification failed. Please check the errors above."
        exit 1
    fi
}

# Run main function
main "$@"