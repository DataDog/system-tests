#!/bin/bash

# Script to check that all base image versions match build_python_base_images.sh

set -e

BUILD_SCRIPT="utils/build/build_python_base_images.sh"

if [ ! -f "$BUILD_SCRIPT" ]; then
    echo "Error: $BUILD_SCRIPT not found"
    exit 1
fi

echo "Checking image version consistency..."

# Extract canonical versions from build script (only before if statement)
canonical_images=$(sed -n '1,/^if \[/p' "$BUILD_SCRIPT" | grep -o "datadog/system-tests:[^[:space:]]*base-v[0-9]\{1,\}" | sort -u)

echo "Canonical versions from $BUILD_SCRIPT:"
echo "$canonical_images"
echo

# Get all files with base image references (excluding build script)
all_files=$(grep -Erl "datadog/system-tests:.*base-v" . | grep -v "$BUILD_SCRIPT")

exit_code=0

for canonical_tag in $canonical_images; do
    image_name=$(echo "$canonical_tag" | sed 's|datadog/system-tests:||' | sed -E 's|-v[0-9]+||')
    canonical_version=$(echo "$canonical_tag" | grep -o "v[0-9]\{1,\}")
    
    echo "Checking $image_name (expected: $canonical_version)"
    
    # Find all occurrences of this image in other files
    while IFS= read -r file; do
        if [ -n "$file" ]; then
            # Get all versions of this image in the file
            versions=$(grep -o "datadog/system-tests:$(echo "$image_name" | sed 's/\./\\./g')-v[0-9]\{1,\}" "$file" 2>/dev/null || true)
            
            if [ -n "$versions" ]; then
                for version_tag in $versions; do
                    found_version=$(echo "$version_tag" | grep -o "v[0-9]\{1,\}")
                    if [ "$found_version" != "$canonical_version" ]; then
                        echo "  ❌ MISMATCH in $file: found $found_version, expected $canonical_version"
                        exit_code=1
                    else
                        echo "  ✅ OK in $file: $found_version"
                    fi
                done
            fi
        fi
    done <<< "$all_files"
    
    # Also check the if block in the build script itself
    echo "  Checking if block in $BUILD_SCRIPT"
    escaped_name=$(echo "$image_name" | sed 's/\./\\./g')
    if_versions=$(sed -n '/^if \[/,/^fi/p' "$BUILD_SCRIPT" | grep -o "datadog/system-tests:${escaped_name}-v[0-9]\{1,\}" 2>/dev/null || true)
    
    if [ -n "$if_versions" ]; then
        for version_tag in $if_versions; do
            found_version=$(echo "$version_tag" | grep -o "v[0-9]\{1,\}")
            if [ "$found_version" != "$canonical_version" ]; then
                echo "  ❌ MISMATCH in if block of $BUILD_SCRIPT: found $found_version, expected $canonical_version"
                exit_code=1
            else
                echo "  ✅ OK in if block of $BUILD_SCRIPT: $found_version"
            fi
        done
    fi
done

if [ $exit_code -eq 0 ]; then
    echo
    echo "✅ All image versions are consistent!"
else
    echo
    echo "❌ Version mismatches found!"
fi

exit $exit_code
