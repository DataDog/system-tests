import logging
import logging.config


def vm_logger(host_log_folder, log_name, level=logging.INFO, log_folder=None, show_timestamp=True):
    output_folder = log_folder or host_log_folder
    specified_logger = logging.getLogger(log_name)
    if len(specified_logger.handlers) == 0:
        formatter = logging.Formatter("%(asctime)s:%(message)s", "%Y-%m-%d %H.%M.%S")
        handler = logging.FileHandler(f"{output_folder}/{log_name}.log")
        if show_timestamp:
            handler.setFormatter(formatter)
        specified_logger.setLevel(level)
        specified_logger.addHandler(handler)

    return specified_logger
