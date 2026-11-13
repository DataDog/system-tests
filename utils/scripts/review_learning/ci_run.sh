#!/usr/bin/env bash
# Entry point of the monthly review_learning GitLab job (see .gitlab-ci.yml and docs/ai/review-learning.md).
# 1. The model runs the review-learn skill in report mode, with a read-only GitHub token.
# 2. After the model is done, this script applies the accepted changes and opens a draft pull request.
#    open_pr.py asks for its own write token, so the model never holds one.
# The image is utils/ci/gitlab/docker/review-learning.Dockerfile.
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
# named steps of the skill: never a new script. The model cannot run apply: this script runs it after the model.
# --allowedTools only adds permissions, and .claude/settings.json sets acceptEdits. So dontAsk is required: it refuses
# every tool that is not in the list. --strict-mcp-config skips the MCP servers of the project.
STEPS=(collect filter szz prepare verify_quotes plain_english decide)
ALLOWED=("Read" "Glob" "Grep" "Skill" "Agent" "Task" "Write(./.review-learning/**)" "Edit(./.review-learning/**)")
for step in "${STEPS[@]}"; do
    ALLOWED+=("Bash(venv/bin/python -m utils.scripts.review_learning.${step}:*)")
done
ALLOWED+=("Bash(venv/bin/python --version)" "Bash(gh auth status)" "Bash(git rev-parse --is-shallow-repository)")
ALLOWED+=("Bash(git fetch origin main)" "Bash(se --help)")

claude -p "/system-tests-review-learn ${WINDOW}" --permission-mode dontAsk --strict-mcp-config --allowedTools "${ALLOWED[@]}" \
    | tee .review-learning/claude-output.txt

# Fail the job when the skill did not produce a report.
# A run folder is .review-learning/<start>..<end>, so the name order is the date order.
RUN_DIR="$(find .review-learning -mindepth 1 -maxdepth 1 -type d -name '*..*' | sort | tail -1)/"
ls "${RUN_DIR}report.md" >/dev/null

# No model from here on.
venv/bin/python -m utils.scripts.review_learning.apply --run "$RUN_DIR"
venv/bin/python -m utils.scripts.review_learning.open_pr --run "$RUN_DIR"
