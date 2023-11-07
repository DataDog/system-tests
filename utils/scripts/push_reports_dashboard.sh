#!/bin/bash
set -eu

echo "Launching push results script"
base_path=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)
echo "Current dir:"
pwd
echo "Content dir:"
ls
cd "$base_path"
echo "New dir:  $base_path"
mkdir system-tests-dashboard
git clone https://"${GITHUB_USER}":"${GITHUB_TOKEN}"@github.com/DataDog/system-tests-dashboard.git system-tests-dashboard
echo "Content after clone:"
ls
echo "system test reports folder content:"
ls reports/
echo "Ok  copying:::"
cd reports && cp -v -R --parents "**/*.json" ../system-tests-dashboard/reports/ && cd ..
cd system-tests-dashboard

#git config user.name "${GITHUB_USER}"
#git config user.email "${GITHUB_MAIL}"

#git pull #avoid problems with multiple pushes at same time 
#git add reports/
#git commit -m "add onboarding report"  
#git push
echo "DONE Reports commited to system-tests-dashboard!"