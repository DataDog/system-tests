import logging
import logging.config


def k8s_logger(log_folder, test_name, log_name, level=logging.INFO):
    specified_logger = logging.getLogger(f"{test_name}_{log_name}")
    if len(specified_logger.handlers) == 0:
        formatter = logging.Formatter("%(message)s")
        handler = logging.FileHandler(f"{log_folder}/{log_name}.log")
        handler.setFormatter(formatter)
        specified_logger.setLevel(level)
        specified_logger.addHandler(handler)

    return specified_logger
