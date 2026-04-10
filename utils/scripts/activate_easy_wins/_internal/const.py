from pathlib import Path


ARTIFACT_URL = (
    "https://api.github.com/repos/DataDog/system-tests-dashboard/actions/workflows/nightly.yml/runs?per_page=1"
)

SKIPPED_NODES_FILE = Path("utils/scripts/activate_easy_wins/skip.yml")
