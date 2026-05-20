import subprocess, os, shlex
from typing import TYPE_CHECKING
from utils._logger import logger
from retry import retry

if TYPE_CHECKING:
    from utils.k8s_lib_injection.k8s_cluster_provider import K8sClusterInfo


def execute_command(
    command: str,
    timeout: int | None = None,
    logfile: str | None = None,
    subprocess_env: dict[str, str] | None = None,
    *,
    quiet: bool = False,
) -> str | None:
    """Run a shell command with a timeout.

    Drains stdout/stderr concurrently to avoid pipe-buffer deadlocks on
    verbose commands (e.g. `helm install --debug` on large charts).
    """
    applied_timeout = 90 if timeout is None else timeout

    logger.debug(f"Launching Command: {command} ")

    if not subprocess_env:
        subprocess_env = os.environ.copy()

    output = ""
    try:
        if logfile:
            with open(logfile, "w") as log_file_handle:
                try:
                    subprocess.run(
                        shlex.split(command),
                        stdout=log_file_handle,
                        stderr=log_file_handle,
                        env=subprocess_env,
                        timeout=applied_timeout,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    if timeout is None:
                        return None
                    raise Exception(f"Command: {command} timed out after {applied_timeout} seconds") from None
            return output

        try:
            result = subprocess.run(
                shlex.split(command),
                capture_output=True,
                env=subprocess_env,
                timeout=applied_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            if timeout is None:
                return None
            raise Exception(f"Command: {command} timed out after {applied_timeout} seconds") from None

        output = result.stdout.decode("utf-8", errors="replace")
        if not quiet:
            logger.debug(f"Command: {command} \n {output}")
        else:
            logger.info(f"Command: {command}")
        if result.returncode != 0:
            output_error_str = result.stderr.decode("utf-8", errors="replace")
            logger.debug(f"Command: {command} \n {output_error_str}")
            raise Exception(f"Error executing command: {command} \nStdout: {output}\nStderr: {output_error_str}")

    except Exception as ex:
        logger.error(f"Error executing command: {command} \n {ex}")
        raise

    return output


@retry(delay=1, tries=5)
def helm_add_repo(name: str, url: str, k8s_cluster_info: "K8sClusterInfo", *, update: bool = False) -> None:
    logger.info(f"Adding helm repo {name} with url {url} for cluster {k8s_cluster_info.cluster_name}")
    execute_command(f"helm repo add {name} {url}")
    if update:
        execute_command(f"helm repo update")


@retry(delay=1, tries=5)
def helm_install_chart(
    host_log_folder: str,
    k8s_cluster_info: "K8sClusterInfo",
    name: str,
    chart: str,
    set_dict: dict[str, str] = {},
    value_file: str | None = None,
    *,
    upgrade: bool = False,  # noqa: ARG001  # unused; retained for call-site compatibility
    timeout: int | None = 90,
    namespace: str = "datadog",
    chart_version: str | None = None,
) -> None:
    # Copy and replace cluster name in the value file
    custom_value_file = None
    if value_file:
        with open(value_file) as file:
            value_data = file.read()

        value_data = value_data.replace("$$CLUSTER_NAME$$", str(k8s_cluster_info.cluster_name))

        custom_value_file = f"{host_log_folder}/{k8s_cluster_info.cluster_name}_help_values.yaml"

        with open(custom_value_file, "w") as fp:
            fp.write(value_data)
            fp.seek(0)

    set_str = ""
    if set_dict:
        for key, value in set_dict.items():
            set_str += f" --set {key}={value}"

    wait = "--wait"
    if timeout == 0 or timeout is None:
        wait = ""

    version_str = f" --version {chart_version}" if chart_version else ""

    # Always use `helm upgrade --install` so that retries are idempotent: if a previous
    # attempt left a release record (e.g. timed out after creating resources), the next
    # attempt upgrades it instead of failing with "cannot re-use a name that is still in use".
    if custom_value_file:
        command = (
            f"helm upgrade {name} --install {wait} {set_str} --debug -f {custom_value_file} "
            f"{chart}{version_str} --namespace={namespace}"
        )
    else:
        command = f"helm upgrade {name} --install --debug {wait} {set_str} {chart}{version_str} --namespace={namespace}"
    execute_command("kubectl config current-context")
    execute_command(command, timeout=timeout, quiet=True)  # Too many traces to show in the logs
