#!/bin/bash

# Ensure aws-cli and jq are installed
if ! command -v aws &> /dev/null; then
    echo "ERROR: aws-cli could not be found, please install it first."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "ERROR: jq could not be found, please install it first."
    exit 1
fi

# SSO profile and parameters
SSO_PROFILE="default"
SSO_REGION="us-east-1"
SSO_ACCOUNT_ID="601427279990"
SSO_ROLE_NAME="account-admin"

# Configure SSO profile without prompts
aws configure set sso_region $SSO_REGION --profile $SSO_PROFILE
aws configure set sso_account_id $SSO_ACCOUNT_ID --profile $SSO_PROFILE
aws configure set sso_role_name $SSO_ROLE_NAME --profile $SSO_PROFILE


# Check for a valid accessToken
CACHE_DIR="$HOME/.aws/sso/cache"
ACCESS_TOKEN=""

# Find cached AWS SSO JSON files
json_files=()
while IFS= read -r -d $'\0'; do
    json_files+=("$REPLY")
done < <(find "$CACHE_DIR" -name '*.json' -print0 2>/dev/null)

# Check if the array is empty or if the cached SSO files exist
if [ ${#json_files[@]} -eq 0 ]; then
    echo ""
else
    for file in "${json_files[@]}"; do
        token=$(jq -r '.accessToken // empty' "$file")
        if [ -n "$token" ]; then
            ACCESS_TOKEN="$token"
            break
        fi
    done
fi

# Try an AWS command to check if the accessToken is still valid, or login if not
if [ -n "$ACCESS_TOKEN" ]; then
    # Temporarily disable exit on error and check if login with cached credentials works
    set +e
    SSO_ACCOUNT=$(aws sts get-caller-identity --profile $SSO_PROFILE)
    if [ ${#SSO_ACCOUNT} -eq 14 ];  then
        echo "AWS SSO session still valid."
        echo ""
    else
        echo ""
        echo "AWS SSO session looks like its expired. Logging in..."
        aws sso login --profile "$SSO_PROFILE"
    fi

    set -e
else
    echo "AWS SSO, no valid accessToken found. Logging in..."
    aws sso login --profile "$SSO_PROFILE"
fi

# Fetch the accessToken again as it might have been updated
for file in "${CACHE_DIR}"/*.json; do
    if [ -f "$file" ]; then
        token=$(jq -r '.accessToken // empty' "$file")
        if [ -n "$token" ]; then
            ACCESS_TOKEN="$token"
            break
        fi
    fi
done

if [ -z "$ACCESS_TOKEN" ]; then
    echo "No valid accessToken found after login."
    exit 1
fi

# Use the AWS CLI to get temporary credentials associated with the SSO session
CREDENTIALS=$(aws sso get-role-credentials --profile "$SSO_PROFILE" --account-id $SSO_ACCOUNT_ID --role-name $SSO_ROLE_NAME --access-token "$ACCESS_TOKEN")

if [ -z "$CREDENTIALS" ]; then
    echo "Failed to retrieve credentials for profile $SSO_PROFILE"
    exit 1
fi

# Parse JSON response to set environment variables
AWS_ACCESS_KEY_ID=$(echo "$CREDENTIALS" | jq -r '.roleCredentials.accessKeyId')
AWS_SECRET_ACCESS_KEY=$(echo "$CREDENTIALS" | jq -r '.roleCredentials.secretAccessKey')
AWS_SESSION_TOKEN=$(echo "$CREDENTIALS" | jq -r '.roleCredentials.sessionToken')

export SYSTEM_TESTS_AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
export SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
export SYSTEM_TESTS_AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN}

echo ""
echo "Datadog APM System Tets AWS Environment Variables Set:"
echo ""
echo "SYSTEM_TESTS_AWS_ACCESS_KEY_ID=$(echo "${SYSTEM_TESTS_AWS_ACCESS_KEY_ID}" | cut -c1-3)******"
echo "SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY=$(echo "${SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY}" | cut -c1-3)******"
echo "SYSTEM_TESTS_AWS_SESSION_TOKEN=$(echo "${SYSTEM_TESTS_AWS_SESSION_TOKEN}" | cut -c1-3)******"
echo ""
echo "AWS credentials have been set. You can now run your tests."
echo ""