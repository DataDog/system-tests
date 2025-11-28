#!/bin/bash

# Script to sync all base image versions to match build_python_base_images.sh

set -e

BUILD_SCRIPT="utils/build/build_python_base_images.sh"

if [ ! -f "$BUILD_SCRIPT" ]; then
    echo "Error: $BUILD_SCRIPT not found"
    exit 1
fi

echo "Extracting image versions from $BUILD_SCRIPT..."

# Extract image names and versions from build script (only before the if statement)
images=$(sed -n '1,/^if \[/p' "$BUILD_SCRIPT" | grep -o "datadog/system-tests:[^[:space:]]*base-v[0-9]\{1,\}" | sort -u)

echo "Found images to sync:"
echo "$images"
echo

# Get all files that need updating (excluding the build script itself)
files_to_update=$(grep -rl "datadog/system-tests:.*base-v" . | grep -v "$BUILD_SCRIPT")

for image_tag in $images; do
    # Extract image name (without datadog/system-tests: prefix)
    full_name_with_version=${image_tag#datadog/system-tests:}
    image_name=$(echo "$full_name_with_version" | sed -E 's/-v[0-9]+$//')
    new_version=$(echo "$full_name_with_version" | grep -o "v[0-9]\{1,\}")

    echo "Syncing $image_name to $new_version"

    # Escape dots in image name for regex
    escaped_name=${image_name//./\\.}

    # Update all files containing this image
    echo "$files_to_update" | xargs grep -l "datadog/system-tests:${escaped_name}-v" 2>/dev/null | while read -r file; do
        echo "  Updating $file"
        sed -E -i.bak "s|datadog/system-tests:${escaped_name}-v[0-9]+|datadog/system-tests:${image_name}-${new_version}|g" "$file"
        rm -f "$file.bak"
    done

    # Also update the if block in the build script itself
    echo "  Updating if block in $BUILD_SCRIPT"
    sed -E -i.bak "s|datadog/system-tests:${escaped_name}-v[0-9]+|datadog/system-tests:${image_name}-${new_version}|g" "$BUILD_SCRIPT"
    rm -f "$BUILD_SCRIPT.bak"
done

echo "All image versions synced to $BUILD_SCRIPT successfully!"
