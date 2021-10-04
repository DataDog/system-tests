import os
import json

from flask import Flask, send_from_directory, request, render_template
from utils.interfaces._schemas_validators import _get_schemas_store, _get_schemas_filenames
from json_schema_for_humans.generate import generate_from_schema, generate_from_filename
import json_schema_for_humans


static_folder = os.path.join(json_schema_for_humans.__path__[0], "templates/js")
template_folder = os.path.join(os.getcwd(), "utils/interfaces/schemas")

app = Flask(__name__, static_url_path="/static", static_folder=static_folder, template_folder=template_folder)

store = _get_schemas_store()

documentations = {}

for filename in _get_schemas_filenames():
    if filename.endswith("request.json"):
        doc = generate_from_schema(filename, store)
        doc = doc.replace("schema_doc.css", "/static/schema_doc.css")
        doc = doc.replace("schema_doc.min.js", "/static/schema_doc.min.js")
        documentations[filename[len("utils/interfaces/schemas") :]] = doc


@app.route("/", methods=["GET"])
def default():

    data = {"schemas": []}

    for filename in documentations:
        doc_path = filename.replace(".json", ".html")
        # doc_path = doc_path[len("utils/interfaces/schemas"):]
        # filename = filename[len("utils/interfaces/schemas"):]

        data["schemas"].append({"href": f"{doc_path}", "caption": filename})

    return render_template("index.html", data=data)


@app.route("/<path:path>.html", methods=["GET"])
def documentation(path):
    path = f"/{path}.json"

    print(path)
    print(documentations.keys())

    if path not in documentations:
        return "File not found", 404

    return documentations[path]


if __name__ == "__main__":
    app.run(port=8080, debug=True)
