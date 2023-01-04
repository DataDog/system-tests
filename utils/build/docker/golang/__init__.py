from utils.docker import dockerfile, import_in_path_dockerfiles

# specififying files to be included, can improve the performance of the build slightly as other files in the repository will be ignored
chi_optimized = dockerfile("chi.Dockerfile").isolated_paths("utils/build/docker/golang/install_ddtrace.sh", "utils/build/docker/golang/app")
# on linux system, this gives 100msec speedup on subsequent rebuilds 


# imports all docker files in current directory as python objects e.g. chi.Dockerfile turns into util.build.docker.golang.chi attribute
import_in_path_dockerfiles()