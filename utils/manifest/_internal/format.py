from pathlib import Path
import re


def yml_sort(directory: Path = Path("manifests/")) -> None:
    for file in directory.iterdir():
        manifest_data: list[tuple[str, list[str]]] = []
        header_data = []
        if file.is_dir():
            continue

        in_manifest = False
        for line in file.read_text().splitlines():
            if line == "manifest:":
                in_manifest = True
                header_data.append(line)
                continue
            if not in_manifest:
                header_data.append(line)
                continue

            if line.startswith(("    ", "  :")) or re.match(r" *\#", line):
                manifest_data[-1][1].append(line)
            else:
                manifest_data.append((line, []))

        manifest_data.sort(
            key=lambda x: x[0][x[0].find("tests/") : x[0].rfind(":")]
            if not x[0].startswith("  ?")
            else x[0][x[0].find("tests/") :]
        )

        text = ""
        for line in header_data:
            text += f"{line}\n"

        for rule in manifest_data:
            text += f"{rule[0]}\n"
            for line in rule[1]:
                text += f"{line}\n"

        file.write_text(text)


if __name__ == "__main__":
    yml_sort()
