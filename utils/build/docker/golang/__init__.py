from utils.docker import dockerfile
from utils import project_root

chi = dockerfile("chi.Dockerfile")
chi_optimized = dockerfile("chi.Dockerfile").isolated_paths("utils/build/docker/golang/install_ddtrace.sh", "utils/build/docker/golang/app")
