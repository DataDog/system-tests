import logging

from ddtrace import tracer

from pylons import request, response, session, tmpl_context as c, url
from pylons.controllers.util import abort, redirect

from app.lib.base import BaseController, render

log = logging.getLogger(__name__)


class WafController(BaseController):
    def index(self):
        span = tracer.start_span("my_operation_name")
        span.set_tag("my_interesting_tag", "my_interesting_value")
        span.finish()

        return "Hello World"
