import yaml
import os
import sys


def sort_keys(obj: dict, path="") -> dict:
    sorted_keys = sorted(obj.keys(), key=lambda k: (not k.endswith("/"), k))
    sorted_obj = {}
    for key in sorted_keys:
        if isinstance(obj[key], dict):
            sorted_obj[key] = sort_keys(obj[key], f"{path}{key}/")
        else:
            sorted_obj[key] = obj[key]
    return sorted_obj


def process_yaml_file(file_path: str):
    with open(file_path, "r") as file:
        data = yaml.safe_load(file)
    sorted_data = sort_keys(data)
    with open(file_path, "w") as file:
        yaml.dump(sorted_data, file, sort_keys=False)


def main(folder_path: str):
    for filename in os.listdir(folder_path):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            full_path = os.path.join(folder_path, filename)
            print("sorting: ", full_path)
            process_yaml_file(full_path)


if __name__ == "__main__":
    main(sys.argv[1])
