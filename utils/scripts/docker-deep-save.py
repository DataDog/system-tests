from pathlib import Path
from argparse import ArgumentParser, Namespace
import tarfile
import os
import tempfile
from tempfile import _TemporaryFileWrapper
import json
from subprocess import check_output, CalledProcessError


def parse_args() -> Namespace:
    parser = ArgumentParser(Path(__file__).name)
    parser.add_argument(
        "image", type=str, help="The docker image to save",
    )
    parser.add_argument(
        "-o", "--output", type=Path, help="Where to save the extracted image", default=Path("./deep-save-image"),
    )

    return parser.parse_args()


def create_output_directory(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)


def save_image(image: str, output: _TemporaryFileWrapper) -> None:
    print("saving docker image...")
    check_output(
        ["docker", "save", image, "--output", output.name,]
    )


def extract_tar(tar_file: _TemporaryFileWrapper, output: Path) -> None:
    print("extracting tar file...")
    with tarfile.open(tar_file.name) as t:
        t.extractall(str(output))

    tar_file.close()
    os.unlink(tar_file.name)


def exctract_layer(layer_path: Path, output: Path) -> None:
    with tarfile.open(str(layer_path)) as t:
        where = layer_path.parent
        print(f" - extracting {output}")
        t.extractall(str(output))


def get_layers_from_manifest(output: Path) -> list[Path]:
    print("parsing manifest.json...")
    manifest_path = output / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("no manifest file in the output directory")

    with manifest_path.open("r") as f:
        manifest_data = json.load(f)

    layers: list[Path] = []

    for image in manifest_data:
        for layer in image.get("Layers"):
            layer_path = output.joinpath(*layer.split(os.sep))
            layers.append(layer_path)

    return layers


def main() -> None:
    args = parse_args()

    image: str = args.image
    output: Path = args.output
    temp_image_file = tempfile.NamedTemporaryFile(delete=False)

    try:
        save_image(image, temp_image_file)
    except CalledProcessError:
        exit(1)

    create_output_directory(output)
    extract_tar(temp_image_file, output)

    print("extracting layers...")
    for layer in get_layers_from_manifest(output):
        exctract_layer(layer, output)
        os.remove(str(layer))

    print("done!")


if __name__ == "__main__":
    main()
