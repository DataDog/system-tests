from threading import RLock
from pprint import pp
import utils
default = utils._context._scenarios.scenarios.default
setattr(utils._context.core.context, 'scenario', default)
from utils._context.component_version import ComponentVersion
default.weblog_container._library = ComponentVersion('ruby', '42')
default.weblog_container.image.env = {'a': 42}
print(utils._context.core.context)

from tests.debugger import test_debugger_expression_language

test = test_debugger_expression_language.Test_Debugger_Expression_Language()
pp(default.get_warmups())

for c in default._required_containers:
    c._starting_lock = RLock()

default._start_containers()
