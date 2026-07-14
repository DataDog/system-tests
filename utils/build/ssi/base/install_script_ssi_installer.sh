#!/bin/bash

set -euo pipefail

DD_INSTALL_ONLY=true DD_INSTALLER=true bash -c "$(cat install_script_agent7.sh)"
