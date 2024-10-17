#!/bin/bash
echo "START ruby APP"

# shellcheck disable=SC2035
sudo chmod -R 755 *
export PATH=~/.rbenv/bin/:~/.rbenv/shims:$PATH
rbenv local 3.0.2
DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install
current_user=$(whoami)
sed -i "s/SSI_USER/$current_user/g" test-app.service
./create_and_run_app_service.sh "/home/$current_user/.rbenv/shims/rails server -b 0.0.0.0 -p 5985"

echo "RUN ruby DONE"
