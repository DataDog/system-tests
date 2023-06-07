#!/bin/bash
set -eu

base_path=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)
cd $base_path

mkdir system-tests-dashboard
git clone https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/DataDog/system-tests-dashboard.git system-tests-dashboard
cd system-tests-dashboard
git checkout robertomonteromiguel/onboarding_tests_reports
git pull
export SCENARIO_SUFIX=$(echo "$SCENARIO" | tr '[:upper:]' '[:lower:]')
mkdir -p reports/onboarding/$TEST_LIBRARY/$SCENARIO_SUFIX
cp ../logs_${SCENARIO_SUFIX}/report.json reports/onboarding/$TEST_LIBRARY/${SCENARIO_SUFIX}/${SCENARIO_SUFIX}.json
cp ../logs_${SCENARIO_SUFIX}/pulumi_installed_versions.log reports/onboarding/$TEST_LIBRARY/${SCENARIO_SUFIX}/
cp ../logs_${SCENARIO_SUFIX}/vms_desc.log reports/onboarding/$TEST_LIBRARY/${SCENARIO_SUFIX}/
git config user.name ${GITHUB_USER}
git config user.email ${GITHUB_MAIL}
git add reports/onboarding/$TEST_LIBRARY/${SCENARIO_SUFIX}/
git commit -m "add onboarding report"   
git push
echo "DONE Reports commited to system-tests-dashboard!"