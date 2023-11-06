#!/bin/bash
set -eu

base_path=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)
cd "$base_path"

mkdir system-tests-dashboard
git clone https://"${GITHUB_USER}":"${GITHUB_TOKEN}"@github.com/DataDog/system-tests-dashboard.git system-tests-dashboard
cd system-tests-dashboard
#from system-tests/reports to system-tests-dashboard/reports
cp -R ../reports/ reports/

git config user.name "${GITHUB_USER}"
git config user.email "${GITHUB_MAIL}"

git pull #avoid problems with multiple pushes at same time 
git add reports/
git commit -m "add onboarding report"  
git push
echo "DONE Reports commited to system-tests-dashboard!"