from time import time
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import json

from utils.interfaces._core import BaseValidation
from utils import context

TELEMETRY_AGENT_ENDPOINT = "/telemetry/proxy/api/v2/apmtelemetry"
TELEMETRY_INTAKE_ENDPOINT = "/api/v2/apmtelemetry"


# TODO: movethis test logic in test class
class _SeqIdLatencyValidation(BaseValidation):
    """Verify that the messages seq_id s are sent somewhat in-order."""

    MAX_OUT_OF_ORDER_LAG = 0.1  # s
    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self):
        super().__init__()
        self.max_seq_id = 0
        self.received_max_time = None

    def check(self, data):
        seq_id = data["request"]["content"]["seq_id"]
        now = time()
        if seq_id > self.max_seq_id:
            self.max_seq_id = seq_id
            self.received_max_time = now
        else:
            if self.received_max_time is not None and (now - self.received_max_time) > self.MAX_OUT_OF_ORDER_LAG:
                self.set_failure(
                    f"Received message with seq_id {seq_id} to far more than"
                    f"100ms after message with seq_id {self.max_seq_id}"
                )


class _NoSkippedSeqId(BaseValidation):
    """Verify that the messages seq_id s are sent somewhat in-order."""

    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self):
        super().__init__()
        self.seq_ids = []

    def check(self, data):
        if 200 <= data["response"]["status_code"] < 300:
            seq_id = data["request"]["content"]["seq_id"]
            self.seq_ids.append((seq_id, data["log_filename"]))

    def final_check(self):
        self.seq_ids.sort()
        for i in range(len(self.seq_ids) - 1):
            diff = self.seq_ids[i + 1][0] - self.seq_ids[i][0]
            if diff == 0:
                self.set_failure(
                    f"Detected 2 telemetry messages with same seq_id {self.seq_ids[i + 1][1]} and {self.seq_ids[i][1]}"
                )
            elif diff > 1:
                self.set_failure(
                    f"Detected non conscutive seq_ids between {self.seq_ids[i + 1][1]} and {self.seq_ids[i][1]}"
                )


class _AppHeartbeatValidation(BaseValidation):
    """Verify telemetry messages are sent every heartbeat interval."""

    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self):
        super().__init__()
        self.prev_message_time = -1
        self.TELEMETRY_HEARTBEAT_INTERVAL = int(context.weblog_image.env.get("DD_TELEMETRY_HEARTBEAT_INTERVAL", 60))
        self.ALLOWED_INTERVALS = 2
        self.fmt = "%Y-%m-%dT%H:%M:%S.%f"

    def check(self, data):
        curr_message_time = datetime.strptime(data["request"]["timestamp_start"], self.fmt)
        if self.prev_message_time != -1:
            delta = curr_message_time - self.prev_message_time
            if delta > timedelta(seconds=self.ALLOWED_INTERVALS * self.TELEMETRY_HEARTBEAT_INTERVAL):
                self.set_failure(
                    f"No heartbeat or message sent in {self.ALLOWED_INTERVALS} hearbeat intervals: {self.TELEMETRY_HEARTBEAT_INTERVAL}\nLast message was sent {str(delta)} seconds ago."
                )
        self.prev_message_time = curr_message_time

class _AppDependenciesLoadedValidation(BaseValidation):
    """Verify that the dependency telemetry is correct."""
    is_success_on_expiry = True
    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self):
        super().__init__()

        def read_nodejs_dependencies(): 
            file_path = "./utils/build/docker/nodejs/express4/package.json"
            package_file = open(file_path, encoding='UTF-8')
            package_json = json.load(package_file)
            loaded_dependencies = package_json["loaded-dependencies"]
            defined_dependencies = package_json["dependencies"]
            return defined_dependencies, loaded_dependencies

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
                    pass # TODO: throw error for malformatted app.csproj
                if attributes.get("Loaded"):
                    loaded_dependencies[dependency_name] = dependency_version
                defined_dependencies[dependency_name] = dependency_version
            
            return loaded_dependencies, defined_dependencies

        def read_java_dependencies():
            file_path = "./utils/build/docker/java/spring-boot/pom.xml"
            document = ET.parse(file_path)
            root =  document.getroot()

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
            "nodejs" : read_nodejs_dependencies,
            "dotnet": read_dotnet_dependencies,
            "java" : read_java_dependencies
        }

        library = context.library.library
        loaded_dependencies, defined_dependencies = library_dependency_map[library]()


        self.seen_dependencies = {}
        self.seen_loaded_dependencies = {}

        for dependency, version in defined_dependencies.items():
            self.seen_dependencies[dependency] = False

        for dependency, version in loaded_dependencies.items():
            self.seen_loaded_dependencies[dependency] = False

    def check(self, data):
        content = data["request"]["content"]
        if content.get("request_type") == "app-started":
            print("Check load dependency not here")
            if content["payload"].get("dependencies"):
                for dependency in content["payload"]["dependencies"]:
                    dependency_id = dependency["name"] #+dep["version"]
                    assert dependency_id not in self.seen_loaded_dependencies, "Loaded dependency should not be in app-started"
                    if(dependency_id not in self.seen_dependencies):
                        print("not in seen")
                        print(dependency_id)
                    self.seen_dependencies[dependency_id] = True
        elif content.get("request_type") == "app-dependencies-loaded":
            print("Check load dependency is present")
            for dependency in content["payload"]["dependencies"]:
                dependency_id = dependency["name"] #+dependency["version"]
                self.seen_dependencies[dependency_id] = True
                self.seen_loaded_dependencies[dependency_id] = True

    def final_check(self):
        for dependency, seen in self.seen_dependencies.items():
            assert seen, dependency + " was not sent"
        for dependency, seen in self.seen_loaded_dependencies.items():
            assert seen, dependency + " was not sent"