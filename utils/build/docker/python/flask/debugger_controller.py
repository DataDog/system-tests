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

intLocal = 0
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


@debugger_blueprint.route("/pii", methods=["GET"])
def pii():
    pii = Pii()
    customPii = CustomPii()
    value = pii.test_value
    custom_value = customPii.test_value
    return f"PII {value}. CustomPII {custom_value}"


@debugger_blueprint.route("/expression", methods=["GET"])
def expression():
    input_value = request.args.get("inputValue", type=str)
    test_struct = ExpressionTestStruct()
    local_value = len(input_value)
    return f"Great success number {local_value}"


@debugger_blueprint.route("/expression/exception", methods=["GET"])
def expression_exception():
    abort(500, description="Hello from exception")


@debugger_blueprint.route("/expression/operators", methods=["GET"])
def expression_operators():
    int_value = request.args.get("intValue", type=int)
    float_value = request.args.get("floatValue", type=float)
    str_value = request.args.get("strValue", type=str)

    return f"Int value {int_value}. Float value {float_value}. String value is {str_value}."


@debugger_blueprint.route("/expression/strings", methods=["GET"])
def string_operations():
    str_value = request.args.get("strValue", type=str)
    empty_string = request.args.get("emptyString", default="")
    null_string = request.args.get("nullString")

    return f"strValue {str_value}. emptyString {empty_string}. {null_string}."


@debugger_blueprint.route("/expression/collections", methods=["GET"])
def collections_operations():
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
    int_value = request.args.get("intValue", type=int)
    str_value = request.args.get("strValue")
    pii = None

    return f"Pii is null {pii is None}. intValue is null {int_value is None}. strValue is null {str_value is None}."
