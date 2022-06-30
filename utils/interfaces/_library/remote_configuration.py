# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import traceback

from utils.interfaces._core import BaseValidation
from utils.tools import m, logger


class _RemoteConfigurationValidation(BaseValidation):
    """ will run an arbitrary check on profiling data.

        Validator function can :
        * returns true => validation will be validated at the end (but other will also be checked)
        * returns False or None => nothing is done
        * raise an exception => validation will fail
    """

    path_filters = r"/v\d+.\d+/config"

    def __init__(self, validator, is_success_on_expiry=False):
        super().__init__()
        self.validator = validator
        self.is_success_on_expiry = is_success_on_expiry

    def check(self, data):
        try:
            if self.validator(data):
                self.log_debug(f"{self} is validated by {data['log_filename']}")
                self.is_success_on_expiry = True
        except Exception as e:
            logger.exception(f"{m(self.message)} not validated by {data['log_filename']}")
            msg = traceback.format_exception_only(type(e), e)[0]
            self.set_failure(f"{m(self.message)} not validated by {data['log_filename']}: {msg}")
