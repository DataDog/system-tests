#!/usr/bin/env bash
# Destroys the Pulumi stack of the AWS SSI scenarios, i.e. the VM kept alive with ONBOARDING_KEEP_VMS.
#
# A plain `pulumi destroy` from the root of the repository fails with:
#   error: provided project name "system-tests-vms" doesn't match Pulumi.yaml
# or with "no stack named ... found". The stack is created by utils/virtual_machine/aws_provider.py in the
# Pulumi project "system-tests-vms", while the Pulumi.yaml at the root of the repository is the project "main".
# Destroying a stack only needs its state, not its program, so this script runs the destroy from a temporary
# Pulumi project that has the right name.
#
# Usage: utils/scripts/ssi_wizards/destroy_aws_stack.sh [extra pulumi destroy arguments, e.g. --yes]
#
# Environment:
#   AWS_VAULT_PROFILE  aws-vault profile to use, empty to not use aws-vault
#                      (default: sso-dev-apm-dcs-system-tests-account-admin)

set -euo pipefail

# Keep these two values in sync with utils/virtual_machine/aws_provider.py
# (AWSPulumiProvider.stack_name and the project_name used in AWSPulumiProvider.stack_up)
readonly STACK_NAME="system-tests_dev_onboarding"
readonly PROJECT_NAME="system-tests-vms"

AWS_VAULT_PROFILE="${AWS_VAULT_PROFILE-sso-dev-apm-dcs-system-tests-account-admin}"

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

# The passphrase of the stack secrets is stored in .env by the wizard. .env may reference variables that
# are not defined, so nounset is off while loading it.
if [[ -f .env ]]; then
    set +u
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    set -u
fi

PROJECT_DIR="$(mktemp -d)"
trap 'rm -rf "$PROJECT_DIR"' EXIT
printf 'name: %s\nruntime: python\n' "$PROJECT_NAME" >"$PROJECT_DIR/Pulumi.yaml"

pulumi_cmd=(pulumi --cwd "$PROJECT_DIR")

if ! stacks="$("${pulumi_cmd[@]}" stack ls --json 2>&1)"; then
    echo "Could not list the Pulumi stacks:" >&2
    echo "$stacks" >&2
    echo "If you are not logged in to the local backend, run: pulumi login --local" >&2
    exit 1
fi
if ! grep -q "\"name\": \"$STACK_NAME\"" <<<"$stacks"; then
    echo "The stack $STACK_NAME does not exist in the current Pulumi backend: nothing to destroy."
    echo "Current backend: $("${pulumi_cmd[@]}" whoami --verbose 2>/dev/null | grep -i 'backend url' || echo unknown)"
    echo "If your VM was created with another backend, log in to it first (the wizard uses: pulumi login --local)."
    exit 0
fi

destroy_cmd=("${pulumi_cmd[@]}" destroy --stack "$STACK_NAME" "$@")
if [[ -n "$AWS_VAULT_PROFILE" ]]; then
    destroy_cmd=(aws-vault exec "$AWS_VAULT_PROFILE" -- "${destroy_cmd[@]}")
fi

echo "Destroying the Pulumi stack $STACK_NAME (project $PROJECT_NAME)"
"${destroy_cmd[@]}"
echo "Stack $STACK_NAME destroyed. The EC2 instance of the AWS SSI run is gone."
