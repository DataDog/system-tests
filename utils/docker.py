from pathlib import Path, PurePath
import inspect, os, json, tempfile, subprocess
import shutil

class Image(object):
    iid = str

    def __init__(self, iid):
        self.iid = iid

class Dockerfile(object):
    dockerfile = Path
    root_dir = Path

    def __init__(self, dockerfile, target = None, root_dir = None):
        self.dockerfile = dockerfile
        if root_dir:
            self.root_dir = root_dir
        else:
            self.root_dir = dockerfile.parent
        self.fs_dependencies = {}
        self.isolated_build = False

    def isolated_paths_mapped(self, mapped_paths):
        self.isolated_build = True  

        for target, src in mapped_paths.items():
            src_path = Path(src)
            if not src_path.is_absolute():
                parent = Path(inspect.stack()[1].filename).parent
                src_path = parent / src_path
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


    def _isolated_build(self, workdir_path):
        context_path = workdir_path / "context"
        os.makedirs(context_path) 

        files_to_copy = {}
        for target, src in self.fs_dependencies.items():
            files_to_copy[context_path/target] = src

        for target, _ in files_to_copy.items():
            path = target.parent
            os.makedirs(path, exist_ok=True)

        for target, src in files_to_copy.items():
            shutil.copyfile(src, target, follow_symlinks=True)
        print(os.listdir(context_path))

        builder = _CLIBuilder(None)
        res = builder.build(context_path,dockerfile=self.dockerfile)

        return res
    
    def build(self):
        if self.isolated_build:
            temp_dir = tempfile.TemporaryDirectory()
            return self._isolated_build(Path(temp_dir.name))
        else:
            builder = _CLIBuilder(None)
            return builder.build(self.root, dockerfile=self.dockerfile)

    def image(self):
        return self.build()

    def __str__(self):
        return f"Image. Dockerfile: {self.dockerfile}"


def dockerfile(dockerfile, *args, **kwargs):
    dockerfile = Path(dockerfile)
    if not dockerfile.is_absolute():
        parent = Path(inspect.stack()[1].filename).parent
        dockerfile = parent / dockerfile
    return Dockerfile(dockerfile, *args, **kwargs)

import selectors

class _CLIBuilder(object):
    def __init__(self, progress):
        self._progress = progress

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

        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True) as p:
            # out_lines, err_lines = self._read_lines(p)
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


if __name__ == '__main__':
    import sys
    from pydoc import locate

    arg = sys.argv[1]
    dockerfile = locate(arg)
    dockerfile.build()
    