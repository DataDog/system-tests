import logging
import logging.config
from utils import context


def vm_logger(scenario_name, log_name, level=logging.INFO):
    specified_logger = logging.getLogger(log_name)
    if len(specified_logger.handlers) == 0:
        formatter = logging.Formatter("%(asctime)s:%(message)s", "%Y-%m-%d %H.%M.%S")
        handler = logging.FileHandler(f"{context.scenario.host_log_folder}/{log_name}.log")
        handler.setFormatter(formatter)
        specified_logger.setLevel(level)
        specified_logger.addHandler(handler)

    return specified_logger
