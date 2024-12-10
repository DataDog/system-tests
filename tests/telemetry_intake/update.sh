#!/bin/sh

# Define variables
REPO_URL="https://github.com/DataDog/dd-go.git"
TARGET_DIR="$(PWD)/static"
SUBDIR="trace/apps/tracer-telemetry-intake/telemetry-payload/static/"
BRANCH="prod"  # Specify the branch to fetch

echo "$TARGET_DIR"

# Create a temporary directory for cloning
TEMP_DIR=$(mktemp -d)

# Clone with filtering to minimize data (Git 2.19+ required)
git clone --depth 1 --branch "$BRANCH" --filter=blob:none --sparse "$REPO_URL" "$TEMP_DIR"

# Navigate to the temporary directory
cd "$TEMP_DIR" || exit 1

# Enable sparse checkout and set the specific file
git sparse-checkout init --cone
git sparse-checkout set "$SUBDIR"

# Create the target directory structure
mkdir -p "$TARGET_DIR"

# Move the file to the target location
rm -rf "$TARGET_DIR"
mv "$TEMP_DIR/$SUBDIR" "$TARGET_DIR"

# Exit the temporary directory to prevent errors during cleanup
cd - || exit 1

# Clean up the temporary directory
rm -rf "$TEMP_DIR"

echo "Cloned $SUBDIR from the '$BRANCH' branch of $REPO_URL into $TARGET_DIR"
