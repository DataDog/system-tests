from utils.docker import dockerfile
from utils import project_root

library_proxy = dockerfile("library_proxy.Dockerfile", root_dir = project_root).isolated_paths("utils/proxy/forwarder.py", "utils/build/docker/tools/library_proxy.entrypoint.sh")

if __name__ == '__main__':
    print(library_proxy.image())
