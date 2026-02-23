import argparse
from pathlib import Path
from . import *  # noqa: F403


def main() -> None:
    parser = argparse.ArgumentParser(description="Get system-tests constants")
    parser.add_argument("category")
    parser.add_argument("group")
    parser.add_argument("--static", action="store_true")
    args = parser.parse_args()

    export = globals()[args.category].shell_export(args.group)
    if args.static:
        path = Path(f"utils/const/static/{args.category}")
        path.mkdir(parents=True, exist_ok=True)
        path = path.joinpath(args.group)
        path.write_text(export)
    print(export)  # noqa: T201


if __name__ == "__main__":
    main()
