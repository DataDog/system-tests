import ruamel.yaml

# Fix line wrapping bug in ruamel
ruamel.yaml.emitter.Emitter.MAX_SIMPLE_KEY_LENGTH = 1000

class ManifestEditor:
    raw_data: 
def parse_manifest(library: str, path_root: str, yaml: ruamel.yaml.YAML) -> ruamel.yaml.CommentedMap:  # type: ignore[type-arg]
    with open(f"{path_root}/manifests/{library}.yml", encoding="utf-8") as file:
        return yaml.load(file)


def write_manifest(manifest: ruamel.yaml.CommentedMap, outfile_path: str, yaml: ruamel.yaml.YAML) -> None:  # type: ignore[type-arg]
    with open(outfile_path, "w", encoding="utf8") as outfile:
        yaml.dump(manifest, outfile)
