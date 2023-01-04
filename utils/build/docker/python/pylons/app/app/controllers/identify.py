from app.lib.base import BaseController
from pylons import response
from pylons import tmpl_context as c
from ddtrace import tracer

try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None


class IdentifyController(BaseController):
    def index(self):
        set_user(
            tracer,
            user_id="usr.id",
            email="usr.email",
            name="usr.name",
            session_id="usr.session_id",
            role="usr.role",
            scope="usr.scope",
        )
        return "Hello World"

    def propagate(self):
        set_user(
            tracer,
            user_id="usr.id",
            email="usr.email",
            name="usr.name",
            session_id="usr.session_id",
            role="usr.role",
            scope="usr.scope",
            propagate=True,
        )
        return "Hello World"
