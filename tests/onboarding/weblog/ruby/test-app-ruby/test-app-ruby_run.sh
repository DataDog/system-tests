#!/bin/bash
echo "START RUN APP"

sudo cp -R * /home/datadog

# Upgrade RubyGems and Bundler
gem update --system 3.4.1
gem install bundler -v '~> 2.3.26'
mkdir -p "$GEM_HOME" && chmod -R 777 "$GEM_HOME"

sudo cp test-app-ruby.service /etc/systemd/system/test-app-ruby.service

sudo cd /home/datadog/lib_injection_rails_app
sudo bundle install
sudo systemctl daemon-reload
sudo systemctl enable test-app-ruby.service
sudo systemctl start test-app-ruby.service
sudo systemctl status test-app-ruby.service

echo "RUN DONE"