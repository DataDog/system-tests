from flask import Blueprint, request, abort
from debugger.exception_replay import ExceptionReplayPaper, ExceptionReplayRock, ExceptionReplayScissors

exception_replay_blueprint = Blueprint("exceptionreplay", __name__, url_prefix="/exceptionreplay")


@exception_replay_blueprint.route("/simple", methods=["GET"])
def exception_replay_simple():
    raise Exception("simple exception")


@exception_replay_blueprint.route("/recursion", methods=["GET"])
def exception_replay_recursion():
    depth = request.args.get("depth", type=int)

    return exception_replay_recursion_helper(depth - 1)


def exception_replay_recursion_helper(depth):
    if depth > 0:
        return exception_replay_recursion_helper(depth - 1)
    else:
        raise Exception("recursion exception")


@exception_replay_blueprint.route("/inner", methods=["GET"])
def exception_replay_inner():
    try:
        raise Exception("inner exception")
    except Exception as ex:
        raise Exception("outer exception") from ex


@exception_replay_blueprint.route("/rps", methods=["GET"])
def exception_replay_rps():
    shape = request.args.get("shape", default="20", type=str)
    if shape == "rock":
        raise ExceptionReplayRock()
    elif shape == "paper":
        raise ExceptionReplayPaper()
    elif shape == "scissors":
        raise ExceptionReplayScissors()
    return "No exception"
