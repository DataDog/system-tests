#!/bin/bash
echo "START php APP"

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

sudo cp index.php /home/datadog/

echo "Testing weblog with php version:"
sudo php --version
./create_and_run_app_service.sh "php -S 0.0.0.0:5985"
echo "RUN AFTER THE SERVICE"
cat test-app.service
echo "RUN php DONE"
