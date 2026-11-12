#!/bin/bash
echo "START python APP"

set -e

# Configure pyenv if it's installed (needed for some Python versions like 2.7)
if [ -d "/home/datadog/.pyenv" ]; then
  export PATH="/home/datadog/.pyenv/bin:$PATH" 
  eval "$(pyenv init -)"
fi

# shellcheck disable=SC2035
sudo chmod -R 755 * 

sudo cp django_app.py /home/datadog/
sudo cp pip.conf /etc/pip.conf
# Use the same pip3 that sudo will run. Ubuntu 23+ needs --break-system-packages.
# Some unsupported images ship Python without pip; those keep the previous skip.
if sudo pip3 install --help >/dev/null 2>&1; then
  pip_install=(sudo pip3 install)
  if sudo pip3 install --help 2>/dev/null | grep -q -- '--break-system-packages'; then
    pip_install+=(--break-system-packages)
  fi
  # pip 22.3 to 23.1 crashes on JSON simple API pages that serve dist-info-metadata as a dict.
  # Upgrade it to a hash-pinned pip first: hash checking skips the metadata lookup that crashes.
  pip_version=$(sudo pip3 --version | awk '{print $2}')
  if python3 -c 'import sys; v = tuple(int(x) for x in sys.argv[1].split(".")[:2]); sys.exit(not (22, 3) <= v < (23, 2))' "$pip_version"; then
    echo "pip==24.0 --hash=sha256:ba0d021a166865d2265246961bec0152ff124de910c5cc39f1156ce3fa7c69dc" > /tmp/pip-requirements.txt
    "${pip_install[@]}" --require-hashes -r /tmp/pip-requirements.txt
  fi
  "${pip_install[@]}" django
else
  echo "pip3 is not installed; skipping Django install"
fi
./create_and_run_app_service.sh "python -m django runserver 0.0.0.0:5985" "PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=django_app"
echo "RUN python DONE"
