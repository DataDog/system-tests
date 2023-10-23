#!/bin/bash
set -eu

base_path=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)
cd "$base_path"

mkdir system-tests-dashboard
git clone https://"${GITHUB_USER}":"${GITHUB_TOKEN}"@github.com/DataDog/system-tests-dashboard.git system-tests-dashboard
cd system-tests-dashboard
SCENARIO_SUFIX=$(echo "$SCENARIO" | tr '[:upper:]' '[:lower:]')
REPORTS_PATH="reports/$ENV/$TEST_LIBRARY/$WEBLOG"

git config user.name "${GITHUB_USER}"
git config user.email "${GITHUB_MAIL}"
git add "$REPORTS_PATH"
git commit -m "add onboarding report"  
git pull #avoid problems with multiple pushes at same time 
mkdir -p "$REPORTS_PATH"
cp ../logs_"${SCENARIO_SUFIX}"/report.json "$REPORTS_PATH"/"${SCENARIO_SUFIX}".json
git push
echo "DONE Reports commited to system-tests-dashboard!"