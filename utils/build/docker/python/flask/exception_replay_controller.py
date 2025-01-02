from flask import Blueprint, request, abort
from debugger.exception_replay import ExceptionReplayPaper, ExceptionReplayRock, ExceptionReplayScissors
import asyncio

exception_replay_blueprint = Blueprint("exceptionreplay", __name__, url_prefix="/exceptionreplay")


@exception_replay_blueprint.route("/simple", methods=["GET"])
def exceptionReplaySimple():
    raise Exception("simple exception")


@exception_replay_blueprint.route("/recursion", methods=["GET"])
def exceptionReplayRecursion():
    depth = request.args.get("depth", type=int)
    return exceptionReplayRecursionHelper(depth, depth)


def exceptionReplayRecursionHelper(originalDepth, currentDepth):
    if currentDepth > 0:
        return exceptionReplayRecursionHelper(originalDepth, currentDepth - 1)
    else:
        raise Exception(f"recursion exception depth {originalDepth}")


@exception_replay_blueprint.route("/inner", methods=["GET"])
def exceptionReplayInner():
    try:
        raise Exception("inner exception")
    except Exception as ex:
        raise Exception("outer exception") from ex


@exception_replay_blueprint.route("/rps", methods=["GET"])
def exceptionReplayRps():
    shape = request.args.get("shape", default="20", type=str)
    if shape == "rock":
        raise ExceptionReplayRock()
    elif shape == "paper":
        raise ExceptionReplayPaper()
    elif shape == "scissors":
        raise ExceptionReplayScissors()
    return "No exception"


def deep_function_c():
    raise Exception("multiple stack frames exception")


def deep_function_b():
    return deep_function_c()


def deep_function_a():
    return deep_function_b()


@exception_replay_blueprint.route("/multiframe", methods=["GET"])
def exception_replay_multiframe():
    return deep_function_a()


async def _async_throw():
    raise Exception("async exception")


@exception_replay_blueprint.route("/async", methods=["GET"])
async def exception_replay_async():
    return await _async_throw()
