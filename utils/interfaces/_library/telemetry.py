from time import time
import xml.etree.ElementTree as ET
import json

from utils import context

# TODO: movethis test logic in test class
class _SeqIdLatencyValidation:
    """Verify that the messages seq_id s are sent somewhat in-order."""

    MAX_OUT_OF_ORDER_LAG = 0.1  # s

    def __init__(self):
        super().__init__()
        self.max_seq_id = 0
        self.received_max_time = None

    def __call__(self, data):
        seq_id = data["request"]["content"]["seq_id"]
        now = time()
        if seq_id > self.max_seq_id:
            self.max_seq_id = seq_id
            self.received_max_time = now
        else:
            if self.received_max_time is not None and (now - self.received_max_time) > self.MAX_OUT_OF_ORDER_LAG:
                raise Exception(
                    f"Received message with seq_id {seq_id} to far more than"
                    f"100ms after message with seq_id {self.max_seq_id}"
                )


class _NoSkippedSeqId:
    """Verify that the messages seq_id s are sent somewhat in-order."""

    def __init__(self):
        super().__init__()
        self.seq_ids = []

    def __call__(self, data):
        if 200 <= data["response"]["status_code"] < 300:
            seq_id = data["request"]["content"]["seq_id"]
            self.seq_ids.append((seq_id, data["log_filename"]))

    def final_check(self):
        self.seq_ids.sort()
        for i in range(len(self.seq_ids) - 1):
            diff = self.seq_ids[i + 1][0] - self.seq_ids[i][0]
            if diff == 0:
                raise Exception(
                    f"Detected 2 telemetry messages with same seq_id {self.seq_ids[i + 1][1]} and {self.seq_ids[i][1]}"
                )

            if diff > 1:
                raise Exception(
                    f"Detected non conscutive seq_ids between {self.seq_ids[i + 1][1]} and {self.seq_ids[i][1]}"
                )


def read_dependencies():
    def read_nodejs_dependencies():
        file_path = "./utils/build/docker/nodejs/express4/package.json"
        package_file = open(file_path, encoding="UTF-8")
        package_json = json.load(package_file)
        loaded_dependencies = package_json["loaded-dependencies"]
        defined_dependencies = package_json["dependencies"]
        return loaded_dependencies, defined_dependencies

    def read_dotnet_dependencies():
        file_path = "./utils/build/docker/dotnet/app.csproj"
        document = ET.parse(file_path)
        root = document.getroot()

        dependencies = {}
        loaded_dependencies = {}
        for child in root:
            if child.tag == "ItemGroup":
                dependencies = child
            elif child.tag == "loadedDependency":
                loaded_dependencies[child.text] = None

        defined_dependencies = {}
        for dependency in dependencies:
            attributes = dependency.attrib
            dependency_name = attributes.get("Include")
            dependency_version = attributes.get("Version")
            if not dependency_name:
                pass  # TODO: throw error for malformatted app.csproj
            if attributes.get("Loaded"):
                loaded_dependencies[dependency_name] = dependency_version
            defined_dependencies[dependency_name] = dependency_version

        return loaded_dependencies, defined_dependencies

    def read_java_dependencies():
        file_path = "./utils/build/docker/java/spring-boot/pom.xml"
        document = ET.parse(file_path)
        root = document.getroot()

        dependencies = {}
        properties = {}
        for child in root:
            if "dependencies" in child.tag:
                dependencies = child
            if "properties" in child.tag:
                properties = child

        loaded_dependencies = {}
        for element in properties:
            if "loadedDependency" in element.tag:
                loaded_dependencies[element.text] = None
                break

        defined_dependencies = {}
        for dependency in dependencies:
            dependency_name = None
            dependency_version = None
            for element in dependency:
                if "artifactId" in element.tag:
                    dependency_name = element.text
                elif "version" in element.tag:
                    dependency_version = element.text
            if dependency_name in loaded_dependencies:
                loaded_dependencies[dependency_name] = dependency_version
            defined_dependencies[dependency_name] = dependency_version

        return loaded_dependencies, defined_dependencies

    library_dependency_map = {
        "nodejs": read_nodejs_dependencies,
        "dotnet": read_dotnet_dependencies,
        "java": read_java_dependencies,
    }

    library = context.library.library
    loaded_dependencies, defined_dependencies = library_dependency_map[library]()
    return loaded_dependencies, defined_dependencies
