from utils.docker import dockerfile
from utils import project_root

agent = dockerfile("agent.Dockerfile", root_dir = project_root).isolated_paths("utils/scripts/install_mitm_certificate.sh")

