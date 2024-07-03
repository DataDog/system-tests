import json
import glob
import os
import subprocess

import pytest

from utils._context.library_version import LibraryVersion
from utils.tools import logger

from .core import _Scenario, ScenarioGroup


class ParametricScenario(_Scenario):
    class PersistentParametricTestConf(dict):
        """Parametric tests are executed in multiple thread, we need a mechanism to persist each parametrized_tests_metadata on a file"""

        def __init__(self, outer_inst):
            self.outer_inst = outer_inst
            # To handle correctly we need to add data by default
            self.update({"scenario": outer_inst.name})

        def __setitem__(self, item, value):
            super().__setitem__(item, value)
            # Append to the context file
            ctx_filename = f"{self.outer_inst.host_log_folder}/{os.environ.get('PYTEST_XDIST_WORKER')}_context.json"
            with open(ctx_filename, "a") as f:
                json.dump({item: value}, f)
                f.write(",")
                f.write(os.linesep)

        def deserialize(self):
            result = {}
            for ctx_filename in glob.glob(f"{self.outer_inst.host_log_folder}/*_context.json"):
                with open(ctx_filename, "r") as f:
                    fileContent = f.read()
                    # Remove last carriage return and the last comma. Wrap into json array.
                    all_params = json.loads(f"[{fileContent[:-2]}]")
                    # Change from array to unique dict
                    for d in all_params:
                        result.update(d)
            return result

    def __init__(self, name, doc) -> None:
        super().__init__(
            name, doc=doc, github_workflow="parametric", scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.PARAMETRIC]
        )
        self._parametric_tests_confs = ParametricScenario.PersistentParametricTestConf(self)

    @property
    def parametrized_tests_metadata(self):
        return self._parametric_tests_confs

    def configure(self, config):
        super().configure(config)
        assert "TEST_LIBRARY" in os.environ

        # get tracer version info building and executing the ddtracer-version.docker file
        parametric_appdir = os.path.join("utils", "build", "docker", os.getenv("TEST_LIBRARY"), "parametric")
        tracer_version_dockerfile = os.path.join(parametric_appdir, "ddtracer_version.Dockerfile")
        if os.path.isfile(tracer_version_dockerfile):

            logger.stdout(f"Build container to get {os.getenv('TEST_LIBRARY')} library version...")
            # TODO : reuse the image build by the test, it'll save 4 mn on python.
            cmd = [
                "docker",
                "build",
                ".",
                "-t",
                "ddtracer_version",
                "--progress",
                "plain",
                "-f",
                f"{tracer_version_dockerfile}",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

            if result.returncode != 0:
                message = f"======== STDOUT ========\n{result.stdout.decode('utf-8')}\n\n"
                message += f"======== STDERR ========\n{result.stderr.decode('utf-8')}"
                pytest.exit(f"Can't build the tracer version image:\n{message}", 1)

            result = subprocess.run(
                ["docker", "run", "--rm", "-t", "ddtracer_version"],
                cwd=parametric_appdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            if result.returncode != 0:
                message = f"======== STDOUT ========\n{result.stdout.decode('utf-8')}\n\n"
                message += f"======== STDERR ========\n{result.stderr.decode('utf-8')}"
                pytest.exit(f"Can't get the tracer version image:\n{message}", 1)

            self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), result.stdout.decode("utf-8"))
        else:
            self._library = LibraryVersion(os.getenv("TEST_LIBRARY", "**not-set**"), "99999.99999.99999")

        logger.stdout(f"Library: {self.library}")

    def _get_warmups(self):
        result = super()._get_warmups()
        result.append(lambda: logger.stdout(f"Library: {self.library}"))

        return result

    @property
    def library(self):
        return self._library
