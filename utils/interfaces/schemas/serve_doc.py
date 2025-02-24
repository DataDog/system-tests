# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os
from pathlib import Path

from flask import Flask, render_template
from utils.interfaces._schemas_validators import _get_schemas_store
from json_schema_for_humans.generate import generate_from_schema
from json_schema_for_humans.generation_configuration import GenerationConfiguration
import json_schema_for_humans


static_folder = os.path.join(json_schema_for_humans.__path__[0], "templates/js")
template_folder = os.path.join(str(Path.cwd()), "utils/interfaces/schemas")

app = Flask(__name__, static_url_path="/static", static_folder=static_folder, template_folder=template_folder)

store = _get_schemas_store()
store_config = GenerationConfiguration()


@app.route("/", methods=["GET"])
def default():
    data: dict = {"schemas": []}

    for schema_id, schema in store.items():
        # skip some schemas
        if not schema_id.endswith("request.json") and "title" not in schema:
            continue

        doc_path = schema_id.replace(".json", ".html")
        # doc_path = doc_path[len("utils/interfaces/schemas"):]
        # filename = filename[len("utils/interfaces/schemas"):]

        data["schemas"].append({"href": f"{doc_path}", "caption": id})

    return render_template("index.html", data=data)


@app.route("/<path:path>.html", methods=["GET"])
def documentation(path):
    path = f"/{path}.json"

    doc = generate_from_schema(path, store, config=store_config)
    doc = doc.replace("schema_doc.css", "/static/schema_doc.css")
    return doc.replace("schema_doc.min.js", "/static/schema_doc.min.js")


if __name__ == "__main__":
    app.run(port=8080, debug=True)  # noqa: S201
