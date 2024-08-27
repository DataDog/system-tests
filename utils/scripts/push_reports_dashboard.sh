#!/bin/bash
set -eu

echo "Launching push results script"
base_path=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)

cd "$base_path"
echo "Current dir:  $base_path"

mkdir system-tests-dashboard
git clone https://"${GITHUB_USER}":"${GITHUB_TOKEN}"@github.com/DataDog/system-tests-dashboard.git system-tests-dashboard

echo "System test reports folder content:"
ls reports/
echo "Copying reports"
# shellcheck disable=SC2035
cd reports && cp -vR --parents */*/*/*.json ../system-tests-dashboard/reports/
cd ..
cd system-tests-dashboard

git config user.name "${GITHUB_USER}"
git config user.email "${GITHUB_MAIL}"

git pull #avoid problems with multiple pushes at same time
git add reports/
git commit -m "add onboarding report"
git push
echo "DONE Reports commited to system-tests-dashboard!"