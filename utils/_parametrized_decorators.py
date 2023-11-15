import inspect
import pytest
import functools
import inspect
from utils._context.core import context
from utils.tools import logger

sql_parametrized_nodes = {}


def missing_sql_feature(func=None, condition=None, library=None, reason=None):
    if func is None:
        return functools.partial(missing_sql_feature, condition=condition, library=library, reason=reason)

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        return eval_codition(func, condition, "missing_feature", library, reason, *args, **kwargs)

    return decorator


def sql_irrelevant(func=None, condition=None, library=None, reason=None):
    if func is None:
        return functools.partial(sql_irrelevant, condition=condition, library=library, reason=reason)

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        return eval_codition(func, condition, "irrelevant", library, reason, *args, **kwargs)

    return decorator


def sql_bug(func=None, condition=None, library=None, reason=None):
    if func is None:
        return functools.partial(sql_bug, condition=condition, library=library, reason=reason)

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        return eval_codition(func, condition, "bug", library, reason, *args, **kwargs)

    return decorator


def eval_codition(func, condition, condition_type, library, reason, *args, **kwargs):
    """We allway evaluate the condition in same way, but if condition evaluation is true, we mark the tests as xfail or skip"""
    # Library evaluation
    eval_library = True
    if library is not None and context.library != library:
        eval_library = False
    # Condition evaluation
    eval_condition = True
    if condition is not None:
        codition_param_values = {}
        for param_name in inspect.signature(condition).parameters:
            codition_param_values[param_name] = kwargs.get(param_name)
        eval_condition = False if not condition(**codition_param_values) else True

    # Full evaluation and set skip/xpass if needed
    if eval_library and eval_condition:
        full_reason = f"{condition_type}:" if reason is None else f"{condition_type}: {reason}"
        if "irrelevant" == condition_type:
            pytest.skip(full_reason)
        else:
            logger.info(
                f"ADDING MARK REASON: {full_reason}"
            )  # Don't remove this trace, we search for it when we parse json report
            sql_parametrized_nodes[hex(id(args[0]))].add_marker(pytest.mark.xfail(reason=full_reason))

    return func(*args, **kwargs)


@pytest.fixture
def manage_sql_decorators(request):
    """ This fixture add to global map all marked nodes, in order to add pytests marks from decorator"""
    sql_parametrized_nodes[hex(id(request.function.__self__))] = request.node
