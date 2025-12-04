from __future__ import annotations

import argparse
import copy
import json
import os
import zipfile
from enum import Enum
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from utils._context.component_version import Version
from utils.get_declaration import get_rules, match_rule, is_terminal, get_all_nodeids, update_rule
from utils._decorators import CustomSpec
from utils._logger import get_logger
from manifests.parser.core import _load_file

import requests
import ruamel.yaml

ruamel.yaml.emitter.Emitter.MAX_SIMPLE_KEY_LENGTH = 1000
from tqdm import tqdm


if __name__ == "__main__":
    main()
