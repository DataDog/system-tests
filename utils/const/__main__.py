import argparse
from . import *  # noqa: F403


def main() -> None:
    parser = argparse.ArgumentParser(description="Get system-tests constants")
    parser.add_argument("category")
    parser.add_argument("group")
    args = parser.parse_args()

    print(globals()[args.category].shell_export(args.group))  # noqa: T201


if __name__ == "__main__":
    main()
