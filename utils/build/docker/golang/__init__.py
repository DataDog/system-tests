from utils.docker import dockerfile, import_in_path_dockerfiles

chi = dockerfile("chi.Dockerfile")
chi_optimized = dockerfile("chi.Dockerfile").isolated_paths("utils/build/docker/golang/install_ddtrace.sh", "utils/build/docker/golang/app")

import_in_path_dockerfiles()