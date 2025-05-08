from flask import Blueprint, request, abort
from debugger.pii import Pii, CustomPii
from debugger.expression_test_struct import ExpressionTestStruct
from debugger.collection_factory import CollectionFactory

# The `debugger` feature allows attachment to specific lines of code.
# Due to differences in line numbering between libraries,
# 'dummy lines' are used to standardize this functionality.
# dummy line
# dummy line
# dummy line
debugger_blueprint = Blueprint("debugger", __name__, url_prefix="/debugger")

intLocal = 1000
intMixLocal = 0


@debugger_blueprint.route("/log", methods=["GET"])
def log_probe():
    return "Log probe", 200


# dummy line
# dummy line
@debugger_blueprint.route("/metric/<int:id>", methods=["GET"])
def metric_probe(id):
    id += 1
    return f"Metric Probe {id}", 200


# dummy line
# dummy line
@debugger_blueprint.route("/span", methods=["GET"])
def span_probe():
    return "Span probe", 200


# dummy line
# dummy line
@debugger_blueprint.route("/span-decoration/<string:arg>/<int:intArg>", methods=["GET"])
def span_decoration_probe(arg, intArg):
    # global intLocal # fails on evaluation
    intLocal = intArg * len(arg)
    return f"Span Decoration Probe {intLocal}"


# dummy line
# dummy line
@debugger_blueprint.route("/mix/<string:arg>/<int:intArg>", methods=["GET"])
def mix_probe(arg, intArg):
    intMixLocal = intArg * len(arg)
    return f"Mixed result {intMixLocal}"


# dummy line
# dummy line
# dummy line
@debugger_blueprint.route("/pii", methods=["GET"])
def pii():
    pii = Pii()
    customPii = CustomPii()
    value = pii.test_value
    custom_value = customPii.test_value
    return f"PII {value}. CustomPII {custom_value}"  # must be line 64


@debugger_blueprint.route("/expression", methods=["GET"])
def expression():
    inputValue = request.args.get("inputValue", type=str)
    testStruct = ExpressionTestStruct()
    localValue = len(inputValue)
    return f"Great success number {localValue}"


@debugger_blueprint.route("/expression/exception", methods=["GET"])
def expression_exception():
    abort(500, description="Hello from exception")


@debugger_blueprint.route("/expression/operators", methods=["GET"])
def expression_operators():
    intValue = request.args.get("intValue", type=int)
    floatValue = request.args.get("floatValue", type=float)
    strValue = request.args.get("strValue", type=str)
    pii = Pii()

    return f"Int value {intValue}. Float value {floatValue}. String value is {strValue}."


@debugger_blueprint.route("/expression/strings", methods=["GET"])
def string_operations():
    strValue = request.args.get("strValue", type=str)
    emptyString = request.args.get("emptyString", default="")
    nullString = request.args.get("nullString")

    return f"strValue {strValue}. emptyString {emptyString}. {nullString}."


@debugger_blueprint.route("/expression/collections", methods=["GET"])
def collection_operations():
    factory = CollectionFactory()

    a0 = factory.get_collection(0, "array")
    l0 = factory.get_collection(0, "list")
    h0 = factory.get_collection(0, "hash")
    a1 = factory.get_collection(1, "array")
    l1 = factory.get_collection(1, "list")
    h1 = factory.get_collection(1, "hash")
    a5 = factory.get_collection(5, "array")
    l5 = factory.get_collection(5, "list")
    h5 = factory.get_collection(5, "hash")

    a0_count = len(a0)
    l0_count = len(l0)
    h0_count = len(h0)
    a1_count = len(a1)
    l1_count = len(l1)
    h1_count = len(h1)
    a5_count = len(a5)
    l5_count = len(l5)
    h5_count = len(h5)

    return f"{a0_count},{a1_count},{a5_count},{l0_count},{l1_count},{l5_count},{h0_count},{h1_count},{h5_count}."


@debugger_blueprint.route("/expression/null", methods=["GET"])
def nulls():
    intValue = request.args.get("intValue", type=int)
    strValue = request.args.get("strValue", type=str)
    boolValue = request.args.get("boolValue", type=bool)

    pii = None
    if boolValue:
        pii = Pii()

    return f"Pii is null {pii is None}. intValue is null {intValue is None}. strValue is null {strValue is None}."


@debugger_blueprint.route("/budgets/<int:loops>", methods=["GET"])
def budgets(loops):
    for _ in range(loops):
        pass
    return "Budgets", 200
