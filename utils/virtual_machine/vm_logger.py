import logging
import logging.config


def vm_logger(scenario_name, log_name, level=logging.INFO):
    specified_logger = logging.getLogger(log_name)
    if len(specified_logger.handlers) == 0:
        formatter = logging.Formatter("%(message)s")
        handler = logging.FileHandler(f"logs_{scenario_name.lower()}/{log_name}.log")
        handler.setFormatter(formatter)
        specified_logger.setLevel(level)
        specified_logger.addHandler(handler)

    return specified_logger
