#!/bin/bash
echo "START ruby APP"

# shellcheck disable=SC2035
sudo chmod -R 755 *

DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install

# shellcheck disable=SC2035
sudo cp -R * /home/datadog

# shellcheck disable=SC2035
sudo chmod -R 755 /home/datadog

sudo chown -R datadog:datadog /home/datadog
#Ubuntu work without this, but Amazon Linux needs bundle install executed with datadog user
sudo su - datadog -c 'DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install'

./create_and_run_app_service.sh "bin/rails server -b 0.0.0.0 -p 5985"

echo "RUN ruby DONE"
