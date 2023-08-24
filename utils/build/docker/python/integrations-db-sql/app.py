import psycopg2
import requests
from ddtrace import tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from flask import Flask, Response
from flask import request as flask_request


try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None

POSTGRES_CONFIG = dict(
    host="postgres", port="5433", user="system_tests_user", password="system_tests", dbname="system_tests",
)

app = Flask(__name__)

tracer.trace("init.service").finish()


@app.route("/")
def hello_world():
    return "Hello, World!\\n"

@app.route("/db", methods=["GET", "POST", "OPTIONS"])
def db():
    #if "file" not in flask_request.args:
    #   return "Please provide a file parameter", 400
    #filename = flask_request.args.get("file")
    #with open(filename, "r") as f:
    #    return f.read()
    print("REQUEST RECEIUVED!!!!!")
    select()
    return "YEAH"

def createDatabae():
    print("CREATING POSTGRES DATABASE")
    sql = "CREATE TABLE demo(id INT NOT NULL, name VARCHAR (20) NOT NULL, age INT NOT NULL, PRIMARY KEY (ID));"
    postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = postgres_db.cursor()
    cursor.execute(sql)
    postgres_db.commit()
    cursor.close()
    postgres_db.close()
    return Response("OK")


def select():
    sql = "SELECT * from demo"
    postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = postgres_db.cursor()
    cursor.execute(sql)
    cursor.close()
    postgres_db.close()
    return Response("OK")

createDatabae()