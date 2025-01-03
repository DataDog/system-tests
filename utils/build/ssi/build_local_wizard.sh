#!/bin/bash

# Path to the JSON file
JSON_FILE="/tmp/matrix.json"
python utils/docker_ssi/docker_ssi_matrix_builder.py --format json > $JSON_FILE

# Function to get libraries that extend from .base_ssi_job
get_libraries() {
    jq -r 'keys[] | select(. != "stages" and . != "configure" and . != ".base_ssi_job")' "$JSON_FILE"
}

# Function to get available weblogs for a specific library
get_weblogs() {
    local library=$1
    jq -r ".[\"${library}\"].parallel.matrix | map(.weblog) | unique | .[]" "$JSON_FILE"
}

# Function to get available base images for a specific weblog
get_base_images() {
    local library=$1
    local selected_weblog=$2
    jq -r ".[\"${library}\"].parallel.matrix | map(select(.weblog == \"${selected_weblog}\")) | map(.base_image) | unique | .[]" "$JSON_FILE"
}

# Function to get available architectures for a specific weblog and base image
get_architectures() {
    local library=$1
    local selected_weblog=$2
    local selected_base_image=$3
    jq -r ".[\"${library}\"].parallel.matrix | map(select(.weblog == \"${selected_weblog}\" and .base_image == \"${selected_base_image}\")) | map(.arch) | unique | .[]" "$JSON_FILE"
}

# Function to get available installable runtimes for a specific weblog, base image, and architecture
get_installable_runtimes() {
    local library=$1
    local selected_weblog=$2
    local selected_base_image=$3
    local selected_arch=$4
    jq -r ".[\"${library}\"].parallel.matrix | map(select(.weblog == \"${selected_weblog}\" and .base_image == \"${selected_base_image}\" and .arch == \"${selected_arch}\")) | map(.installable_runtime) | unique | .[]" "$JSON_FILE"
}

# Interactive wizard
echo "Welcome to the SSI Wizard!"

# Step 1: Select the library
libraries=( $(get_libraries) )
echo "Please select the library you want to test:"
select TEST_LIBRARY in "${libraries[@]}"; do
    if [[ -n "$TEST_LIBRARY" ]]; then
        echo "You selected: $TEST_LIBRARY"
        break
    else
        echo "Invalid selection. Please try again."
    fi
done

# Step 2: Select the weblog
weblogs=( $(get_weblogs "$TEST_LIBRARY") )
echo "Please select the weblog you want to use:"
select weblog in "${weblogs[@]}"; do
    if [[ -n "$weblog" ]]; then
        echo "You selected: $weblog"
        break
    else
        echo "Invalid selection. Please try again."
    fi
done

# Step 3: Select the base image
base_images=( $(get_base_images "$TEST_LIBRARY" "$weblog") )
echo "Please select the base image you want to use:"
select base_image in "${base_images[@]}"; do
    if [[ -n "$base_image" ]]; then
        echo "You selected: $base_image"
        break
    else
        echo "Invalid selection. Please try again."
    fi
done

# Step 4: Select the architecture
architectures=( $(get_architectures "$TEST_LIBRARY" "$weblog" "$base_image") )
echo "Please select the architecture you want to use:"
select arch in "${architectures[@]}"; do
    if [[ -n "$arch" ]]; then
        echo "You selected: $arch"
        break
    else
        echo "Invalid selection. Please try again."
    fi
done

# Step 5: Select the installable runtime if available
installable_runtimes=( $(get_installable_runtimes "$TEST_LIBRARY" "$weblog" "$base_image" "$arch") )
if [[ ${#installable_runtimes[@]} -gt 0 ]]; then
    echo "Please select the installable runtime you want to use:"
    select installable_runtime in "${installable_runtimes[@]}"; do
        if [[ -n "$installable_runtime" ]]; then
            echo "You selected: $installable_runtime"
            break
        else
            echo "Invalid selection. Please try again."
        fi
    done
else
    echo "No installable runtime available for the selected options."
    installable_runtime=""
fi

# Step 6: Ask for additional parameters
read -p "Enter any extra arguments (or leave blank): " extra_args

# Step 7: Execute the command
CMD=("./run.sh" "DOCKER_SSI" "--ssi-weblog" "$weblog" "--ssi-library" "$TEST_LIBRARY" "--ssi-base-image" "$base_image" "--ssi-arch" "$arch")
if [[ -n "$installable_runtime" ]]; then
    CMD+=("--ssi-installable-runtime" "$installable_runtime")
fi
CMD+=($extra_args)

echo "Executing: ${CMD[*]}"
"${CMD[@]}"