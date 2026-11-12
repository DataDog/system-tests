#!/usr/bin/env bash
# Entry point of the monthly review_learning GitLab job (see .gitlab-ci.yml and docs/ai/review-learning.md).
# It runs the review-learn skill in report mode: it writes .review-learning/<run>/report.md and edits nothing.
# The image is utils/ci/gitlab/docker/review-learning.Dockerfile. The job only holds a read-only GitHub token.
set -euo pipefail

# By default, mine the previous calendar month, so that monthly runs never skip or repeat a day.
FIRST_OF_MONTH="$(date -u +%Y-%m-01)"
DEFAULT_WINDOW="$(date -u -d "$FIRST_OF_MONTH -1 month" +%Y-%m-%d)..$(date -u -d "$FIRST_OF_MONTH -1 day" +%Y-%m-%d)"
WINDOW="${REVIEW_LEARNING_WINDOW:-$DEFAULT_WINDOW}"
echo "Review learning window: $WINDOW"

# The skill runs venv/bin/python from the repository root. The image has no system-tests packages, so install them.
python3.12 -m venv venv
venv/bin/pip install --quiet --requirement requirements.txt

# Read-only GitHub token for collect.py and gh, revoked when the script ends.
GH_TOKEN="$(dd-octo-sts token --scope DataDog/system-tests --policy self.gitlab-review-learning)"
export GH_TOKEN
trap 'dd-octo-sts revoke -t "$GH_TOKEN" || true' EXIT

# AI gateway token. authanywhere prints "Authorization: Bearer <token>".
ARCH="$(uname -m | sed 's/x86_64/amd64/; s/aarch64/arm64/')"
curl --retry 5 -fsSLo /tmp/authanywhere "https://binaries.ddbuild.io/dd-source/authanywhere/LATEST/authanywhere-linux-${ARCH}"
chmod +x /tmp/authanywhere
RAW_TOKEN="$(/tmp/authanywhere --audience rapid-ai-platform)"
if [[ "$RAW_TOKEN" != "Authorization: Bearer "* ]]; then
    echo "ERROR: authanywhere printed an unexpected format: ${RAW_TOKEN:0:30}" >&2
    exit 1
fi
export ANTHROPIC_AUTH_TOKEN="${RAW_TOKEN#Authorization: Bearer }"
export ANTHROPIC_BASE_URL="https://ai-gateway.us1.ddbuild.io"
export ANTHROPIC_CUSTOM_HEADERS=$'source: claude\norg-id: 2\nprovider: anthropic\nx-dd-tag-ml_app: system-tests-review-learning\nx-dd-tag-dd.team: system-tests-core'

# szz.py blames the local history, so it needs every merge commit of main.
git fetch --quiet origin main
mkdir -p .review-learning

# Pull request text is untrusted data. So the model can only write inside .review-learning/, and it can only run the
# named steps of the skill: never a new script. apply is not allowed, because this job never edits the rules.
STEPS=(collect filter szz prepare verify_quotes plain_english decide)
ALLOWED=("Read" "Glob" "Grep" "Skill" "Agent" "Task" "Write(./.review-learning/**)" "Edit(./.review-learning/**)")
for step in "${STEPS[@]}"; do
    ALLOWED+=("Bash(venv/bin/python -m utils.scripts.review_learning.${step}:*)")
done
ALLOWED+=("Bash(venv/bin/python --version)" "Bash(gh auth status)" "Bash(git rev-parse --is-shallow-repository)")
ALLOWED+=("Bash(git fetch origin main)" "Bash(se --help)")

claude -p "/system-tests-review-learn ${WINDOW}" --allowedTools "${ALLOWED[@]}" | tee .review-learning/claude-output.txt

# Fail the job when the skill did not produce a report.
ls .review-learning/*/report.md >/dev/null
