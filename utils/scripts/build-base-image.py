#!/usr/bin/env python3
import argparse
import subprocess
import sys

from utils._context.weblog_metadata import WeblogMetaData


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a weblog base image")
    parser.add_argument("library", help="Library name (e.g. nodejs, python)")
    parser.add_argument("weblog", help="Weblog name (e.g. express4, flask-poc)")
    args = parser.parse_args()

    weblogs = WeblogMetaData.load(args.library)
    names = [w.name for w in weblogs]

    if args.weblog not in names:
        print(f"Error: weblog '{args.weblog}' not found for library '{args.library}'")
        print(f"Available weblogs: {', '.join(sorted(names))}")
        sys.exit(1)

    weblog = next(w for w in weblogs if w.name == args.weblog)
    dockerfile = weblog.base_dockerfile
    if dockerfile is None:
        print(f"Error: no base Dockerfile found for {args.weblog}")
        sys.exit(1)

    image_tag = weblog.base_image_tag
    if image_tag is None:
        print(f"Error: could not extract base image tag for {args.weblog}")
        sys.exit(1)

    print(f"Building base image: {image_tag}")
    subprocess.run(["docker", "build", "--progress=plain", "-f", str(dockerfile), "-t", image_tag, "."], check=True)

    print(f"\nDone. To push:\n  docker push {image_tag}")


if __name__ == "__main__":
    main()
