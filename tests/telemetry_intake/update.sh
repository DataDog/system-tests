#!/bin/sh

set -e

# These variables may change over time
# The path in dd-go to the rules JSON files.
# If this script deletes the JSON files in system-tests, it's likely this is no longer valid
SUBDIR="trace/apps/tracer-telemetry-intake/telemetry-payload/static/"
# The "main" branch in dd-go
BRANCH="bm1549/more-missing-configs" # This should ALWAYS be "prod" in master. Please revert changes before merging

# These variables will probably never change
REPO_URL="https://github.com/DataDog/dd-go.git"
SCRIPT_DIR=$(dirname "$(realpath "$0")")
TARGET_DIR="$SCRIPT_DIR/static"

# Create a temporary directory for cloning
TEMP_DIR=$(mktemp -d)

# Clone with filtering to minimize data (Git 2.19+ required)
git clone --depth 1 --branch "$BRANCH" --filter=blob:none --sparse "$REPO_URL" "$TEMP_DIR"

# Navigate to the temporary directory
cd "$TEMP_DIR" || (echo "Failed to navigate to $TEMP_DIR" && exit 1)

# Enable sparse checkout and set the specific file
mkdir -p "$SUBDIR"
git sparse-checkout init --cone
git sparse-checkout set "$SUBDIR"

# This file should not exist in the output
rm "$SUBDIR/_format.py" || (echo "Failed to navigate to $SUBDIR/_format.py" && exit 1)

# Create the target directory structure
mkdir -p "$TARGET_DIR"

# Move the file to the target location
rm -rf "$TARGET_DIR"
mv "$TEMP_DIR/$SUBDIR" "$TARGET_DIR"

# Exit the temporary directory to prevent errors during cleanup
cd - || (echo "Failed to navigate to -" && exit 1)

# Clean up the temporary directory
rm -rf "$TEMP_DIR"

echo "Cloned $SUBDIR from the '$BRANCH' branch of $REPO_URL into $TARGET_DIR"
