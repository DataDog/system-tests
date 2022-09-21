import traceback
from utils.interfaces._core import BaseValidation
from utils.tools import logger, m

TELEMETRY_INTAKE_ENDPOINT = "/api/v2/apmtelemetry"


class _TelemetryValidation(BaseValidation):
    """will run an arbitrary check on telemetry data

    Validator function can :
    * returns true => validation will be validated at the end (but trace will continue to be checked)
    * returns False or None => nothing is done
    * raise an exception => validation will fail
    """

    def __init__(self, validator, is_success_on_expiry=False):
        super().__init__(path_filters=TELEMETRY_INTAKE_ENDPOINT)
        self.validator = validator
        self.is_success_on_expiry = is_success_on_expiry

    def check(self, data):
        try:
            if self.validator(data):
                self.set_status(is_success=True)
        except Exception as e:
            logger.exception(f"{m(self.message)} not validated on {data['log_filename']}")
            msg = traceback.format_exception_only(type(e), e)[0]
            self.set_failure(f"{m(self.message)} not validated on {data['log_filename']}: {msg}")
