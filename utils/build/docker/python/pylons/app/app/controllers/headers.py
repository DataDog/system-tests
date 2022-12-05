from app.lib.base import BaseController
from pylons import response
from pylons import tmpl_context as c


class HeadersController(BaseController):
    def index(self):
        response.headers["content-language"] = "en-US"
        return "Hello World"
