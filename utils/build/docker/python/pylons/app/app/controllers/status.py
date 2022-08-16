import logging

from pylons import request, response, session, tmpl_context as c, url
from pylons.controllers.util import abort, redirect
from webob import Response

from app.lib.base import BaseController, render

log = logging.getLogger(__name__)


class StatusController(BaseController):
    def index(self, *args, **kwargs):
        response.status_code = int(request.params["code"])
        return "Maybe not OK"
