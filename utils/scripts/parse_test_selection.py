from ruamel.yaml import YAML
from utils._context._scenarios import scenario_groups
import os


LIBRARIES = {
        "python",
        "java",
        "golang",
        "cpp"
        }

def parse():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    yml_path = os.path.join(root_dir, 'test-selection.yml')

    yaml = YAML()
    with open(yml_path, 'r') as file:
        return yaml.load(file)["patterns"]

def transform_pattern(pattern: str):
    pattern = pattern.replace(".", r"\.")
    pattern = pattern.replace("*", ".*")
    return pattern

def transform_scenario(val):
    match val:
        case None:
            return
        case "ALL":
            return "ALL"
        case str():
            return getattr(scenario_groups, val)
        case _:
            return [getattr(scenario_groups, scenario) for scenario in val]

def transform_libraries(val):
    match val:
        case None:
            return
        case "ALL":
            return "ALL"
        case str():
            if val in LIBRARIES:
                return val
            else:
                raise Exception(f"Unknown library {val}")
        case list():
            ret = []
            for library in val:
                if library in LIBRARIES:
                    ret.append(library)
                else:
                    raise Exception(f"Unknown library {library}")
            return ret

def get_field(field_name: str, transform_val):
    data = parse()
    ret = {}
    for entry in data:
        pattern = next(iter(entry))
        val = transform_val(entry[pattern].get(field_name, "ALL"))
        if val != "ALL":
            ret[transform_pattern(pattern)] = val
    return ret


def get_libraries():
    return get_field("libraries", transform_libraries)

def get_scenarios():
    return get_field("scenarios", transform_scenario)


def main() -> None:
    print("scenarios")
    print(get_scenarios())
    print("libraries")
    print(get_libraries())



if __name__ == "__main__":
    main()
