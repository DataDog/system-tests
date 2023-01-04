import sys
import types
from pathlib import Path
import inspect
import os
import tempfile
import subprocess
import shutil
from utils import project_root
from pydoc import locate
import tarfile

import docker


class Image(object):
    iid = str

    def __init__(self, iid):
        self.iid = iid

    def modify_image(self, append_from_image=None, append_paths=None, append_paths_mapped=None, env={}):
        dockerfile_contents = ""

        if append_from_image:
            dockerfile_contents += f"FROM {append_from_image.iid} as source_image\n"

        dockerfile_contents += f"FROM {self.iid} as final_image\n"

        if append_from_image:
            dockerfile_contents += "COPY --from=source_image / /"

        if append_paths or append_paths_mapped:
            dockerfile_contents += "COPY / /\n"

        for k, v in env.items():
            dockerfile_contents += f"ENV {k} = {v}\n"

        with tempfile.NamedTemporaryFile() as dockerfile:
            dockerfile.write(dockerfile_contents.encode())
            dockerfile.seek(0)
            d = Dockerfile(Path(dockerfile.name))
            if append_paths:
                d.isolated_paths(*append_paths)
            if append_paths_mapped:
                d.isolated_paths_mapped(append_paths_mapped)

            new_iid = d.build()
            return Image(new_iid)

    # TODO: allow extractting optional files - ie don't error when file is not found
    def extract_files(self, target, paths=[]):
        dockerfile_contents = f"""
FROM {self.iid} as source_image
FROM scratch as target_image
"""
        for path in paths:
            dockerfile_contents += f"COPY --from=source_image {path} /\n"
        with tempfile.NamedTemporaryFile() as dockerfile:
            dockerfile.write(dockerfile_contents.encode())
            dockerfile.seek(0)
            d = Dockerfile(Path(dockerfile.name))
            d.isolated_paths()
            iid = d.build()
            api = docker.from_env()
            image = api.images.get(iid)
            # TODO: poc of data extraction from iamges
            with open(target, 'wb') as output:
                for chunk in image.save():
                    output.write(chunk)

    def cat_file(self, path):
        with tempfile.NamedTemporaryFile() as tar:
            self.extract_files(tar.name, paths = [path])
            t = tarfile.TarFile(tar.name)
            for fname in t.getnames():
                if fname.endswith("/layer.tar"):
                    reader = t.extractfile(fname)
                    inner = tarfile.TarFile(fileobj=reader)
                    output = inner.extractfile(path)
                    return output
                    
    def __str__(self):
        return f"Image: {self.iid}"


class Dockerfile(object):
    dockerfile = Path
    root_dir = Path

    def __init__(self, dockerfile: Path, target=None, root_dir=None):
        self.dockerfile = dockerfile
        if root_dir:
            self.root_dir = root_dir
        else:
            self.root_dir = project_root
        self.fs_dependencies = {}
        self.isolated_build = False

    def isolated_paths_mapped(self, mapped_paths):
        self.isolated_build = True
        root_dir = self.root_dir
        if not root_dir.is_absolute():
            parent = Path(inspect.stack()[1].filename).parent
            root_dir = parent / root_dir

        for target, src in mapped_paths.items():
            src_path = Path(src)
            if not src_path.is_absolute():
                src_path = root_dir / src_path
            self.fs_dependencies[target] = src_path

        return self

    def isolated_paths(self, *paths):
        self.isolated_build = True
        root_dir = self.root_dir
        if not root_dir.is_absolute():
            parent = Path(inspect.stack()[1].filename).parent
            root_dir = parent / root_dir

        for path in paths:
            path = Path(path)
            self.fs_dependencies[path] = root_dir / path

        return self

    def _isolated_build(self, workdir_path, args):
        context_path = workdir_path / "context"
        os.makedirs(context_path)

        files_to_copy = {}
        for target, src in self.fs_dependencies.items():
            files_to_copy[context_path/target] = src

        for target, _ in files_to_copy.items():
            path = target.parent
            os.makedirs(path, exist_ok=True)

        for target, src in files_to_copy.items():
            if src.is_file():
                shutil.copyfile(src, target, follow_symlinks=True)
                shutil.copymode(src, target, follow_symlinks=True)
            else:
                shutil.copytree(src, target)

        builder = _CLIBuilder(None)
        res = builder.build(
            context_path, dockerfile=self.dockerfile, buildargs=args)

        return res

    def build(self, args=None):
        if self.isolated_build:
            temp_dir = tempfile.TemporaryDirectory()
            return self._isolated_build(Path(temp_dir.name), args)
        else:
            builder = _CLIBuilder(None)
            return builder.build(self.root_dir, dockerfile=self.dockerfile, buildargs=args)

    def image(self):
        return Image(self.build())

    def __str__(self):
        return f"Image. Dockerfile: {self.dockerfile}"


def import_in_path_dockerfiles():
    caller_frame = inspect.stack()[1]
    caller_module = inspect.getmodule(caller_frame[0])

    path = Path(caller_module.__file__).parent
    files = list(filter(lambda path: path.lower().endswith(
        ".dockerfile"), os.listdir(path)))

    for file in files:
        attr_name = file[:file.rfind(".")]
        dockerfile = Dockerfile(path / file)
        setattr(caller_module, attr_name, dockerfile)


def dockerfile(dockerfile, *args, **kwargs):
    dockerfile = Path(dockerfile)
    if not dockerfile.is_absolute():
        parent = Path(inspect.stack()[1].filename).parent
        dockerfile = parent / dockerfile
    return Dockerfile(dockerfile, *args, **kwargs)


class _CLIBuilder(object):
    def __init__(self, progress):
        self._progress = progress
        # TODO: this setting should not rely on global env
        self.quiet = False if os.getenv("DOCKER_QUIET") is None else True

    def build(self, path, tag=None,
              nocache=False, pull=False,
              forcerm=False, dockerfile=None, container_limits=None,
              buildargs=None, cache_from=None, target=None):

        if dockerfile:
            dockerfile = os.path.join(path, dockerfile)
        iidfile = tempfile.mktemp()

        command_builder = _CommandBuilder()
        command_builder.add_params("--build-arg", buildargs)
        command_builder.add_list("--cache-from", cache_from)
        command_builder.add_arg("--file", dockerfile)
        command_builder.add_flag("--force-rm", forcerm)
        command_builder.add_flag("--no-cache", nocache)
        command_builder.add_flag("--progress", self._progress)
        command_builder.add_flag("--pull", pull)
        command_builder.add_arg("--tag", tag)
        command_builder.add_arg("--target", target)
        command_builder.add_arg("--iidfile", iidfile)
        args = command_builder.build([path])
        if self.quiet:
            with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True) as p:
                stdout, stderr = p.communicate()
                if p.wait() != 0:
                    # TODO: add better error handling
                    print(f"error building image: {dockerfile}")
                    print("------- STDOUT ---------")
                    print(stdout, end="")
                    print("----------------")
                    print()
                    print("------- STDERR ---------")
                    print(stderr, end="")
                    print("----------------")
        else:
            with subprocess.Popen(args, universal_newlines=True) as p:
                if p.wait() != 0:
                    print("TODO: error building image")

        with open(iidfile) as f:
            line = f.readline()
            image_id = line.split(":")[1].strip()
        os.remove(iidfile)
        return image_id


class _CommandBuilder(object):
    def __init__(self):
        self._args = ["docker", "build"]

    def add_arg(self, name, value):
        if value:
            self._args.extend([name, str(value)])

    def add_flag(self, name, flag):
        if flag:
            self._args.extend([name])

    def add_params(self, name, params):
        if params:
            for key, val in params.items():
                self._args.extend([name, "{}={}".format(key, val)])

    def add_list(self, name, values):
        if values:
            for val in values:
                self._args.extend([name, val])

    def build(self, args):
        return self._args + args


def waf_mutator(image: Image, appsec_rule_version: str):
    with tempfile.NamedTemporaryFile() as version_file:
        version_file.write(appsec_rule_version.encode())
        version_file.seek(0)
        version_file
        paths = {"SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION": version_file.name,
                 "waf_rule_set.json": "binaries/waf_rule_set.json"}
        new_image = image.modify_image(append_paths_mapped=paths, env={
            "DD_APPSEC_RULES": "/waf_rule_set.json",
            "DD_APPSEC_RULESET": "/waf_rule_set.json",
            "DD_APPSEC_RULES_PATH": "/waf_rule_set.json"
        })
        return new_image


def _cli_build_image(args):
    dockerfile: Dockerfile = locate(args.python_path)
    image = dockerfile.image()
    print(image.iid)


def _cli_waf_mutator(args):
    image = Image(args.image)
    mutated_image = waf_mutator(image, args.waf_rule_version)
    print(mutated_image.iid)


def _cli_cat_file(args):
    image = Image(args.image)
    for line in image.cat_file(args.path).readlines():
        print(line.decode("utf-8"))

if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        prog='utils.docker',
        description='system-tests docker utility')
    subparsers = parser.add_subparsers()
    build_parser = subparsers.add_parser("build")
    build_parser.set_defaults(func=_cli_build_image)
    build_parser.add_argument(
        "python_path", help="python resource path to Dockerfile object e.g. utils.build.docker.golang.net-http")

    waf_mutator_parser = subparsers.add_parser("waf_mutate")
    waf_mutator_parser.set_defaults(func=_cli_waf_mutator)
    waf_mutator_parser.add_argument(
        "image", help="docker image identifier e.g. busybox or 18fa1f67c0a3b52e50d9845262a4226a6e4474b80354c5ef71ef27e438c6650b")
    waf_mutator_parser.add_argument(
        "waf_rule_version", help="waf rule version")

    extract_files_parser = subparsers.add_parser("cat_file")
    extract_files_parser.set_defaults(func=_cli_cat_file)
    extract_files_parser.add_argument(
        "image", help="docker image identifier e.g. busybox or 18fa1f67c0a3b52e50d9845262a4226a6e4474b80354c5ef71ef27e438c6650b")
    extract_files_parser.add_argument(
        "path")


    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
