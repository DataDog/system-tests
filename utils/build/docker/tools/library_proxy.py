import docker
import os
from os import path
import tempfile
import shutil
from pathlib import Path, PurePath
import json

current_dir = Path(path.dirname(path.realpath(__file__)))
root_dir = Path(path.realpath(path.join(current_dir, "../../../../")))


def build_image_directly():
    client = docker.APIClient()
    return client.build(path="./", dockerfile=os.path.join(current_dir, "library_proxy.Dockerfile"), tag="ehlo_direct")


def build_image_indirectly():
    work_dir = tempfile.TemporaryDirectory()
    target = Path(work_dir.name)

    files = [
        current_dir / "library_proxy.Dockerfile",
        current_dir / "library_proxy.entrypoint.sh",
        root_dir / "utils/proxy/forwarder.py"
    ]

    dirs_to_create = [f.relative_to(root_dir).parent for f in files]

    for dir in dirs_to_create:
        path = target / dir
        os.makedirs(path, exist_ok=True)

    for file in files:
        target_file = target / file.relative_to(root_dir)
        shutil.copyfile(file, target_file, follow_symlinks=True)

    client = docker.APIClient()
    return client.build(path=target.as_posix(), dockerfile=(current_dir.relative_to(root_dir) / "library_proxy.Dockerfile").as_posix(), tag="ehlo_indirect")


def parse_output(msg):
    msg = json.loads(msg)
    if "stream" in msg:
        print(msg["stream"])
    if "aux" in msg:
        print("Built Image ID: %s" % msg["aux"])
    return msg


def build_and_exec():
    print("building and executing image ======================================")
    image_id = ""
    for msg in build_image_indirectly():
        msg = parse_output(msg)
        if "aux" in msg:
            image_id = msg["aux"].get("ID")
    client = docker.APIClient()

    c = client.create_container(image=image_id, hostname="ehlo", tty=True)
    client.start(c)
    r = client.wait(c)
    print("Container: %s exited with: %s" % (c.get("Id"), r))
    print("Logs: %s(...)" % client.logs(c).decode("utf8")[:100])
    print("======================================")

if __name__ == '__main__':
    import timeit
    build_and_exec()

    print("timing the direct build")
    iterations = 10
    time = timeit.timeit(lambda: build_image_directly(),
                         number=iterations) / iterations
    print("time per iteration: ", time)

    print("timing the docker build that isolates dependencies")
    iterations = 100
    time = timeit.timeit(lambda: build_image_indirectly(),
                         number=iterations) / iterations
    print("time per iteration: ", time)
