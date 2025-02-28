import json

from utils import weblog, interfaces, context, missing_feature, features


# this test relies on the proto file at utils/build/docker/common/message.proto
@features.datastreams_monitoring_protobuf_schema_tracking
class Test_Protobuf:
    def setup_protobuf(self):
        self.serialization_response = weblog.get("/protobuf/serialize")
        self.deserialization_response = weblog.get(f"/protobuf/deserialize?msg={self.serialization_response.text}")

    @missing_feature(
        context.library in ["ruby", "cpp", "golang", "nodejs", "php", "python"],
        reason="no schema tracking for protobuf yet",
    )
    @missing_feature(context.library < "dotnet@3.12.0", reason="wrong schema.name written")
    @missing_feature(context.library < "java@1.47.0", reason="bug on extraction of nested schemas")
    def test_protobuf(self):
        assert self.serialization_response.status_code == 200, self.serialization_response.text
        assert self.deserialization_response.status_code == 200, self.deserialization_response.text

        def validator(trace: list):
            if len(trace) == 1:
                span = trace[0]
            else:
                # find root span
                span = next(s for s in trace if s["parent_id"] == 0)
                # then find child-most span
                while True:
                    child = next((s for s in trace if s["parent_id"] == span["span_id"]), None)
                    if child:
                        span = child
                    else:
                        break

            meta = span.get("meta", {})
            assert "schema.id" in meta
            assert "schema.type" in meta
            assert "schema.definition" in meta
            assert "schema.name" in meta
            assert "schema.operation" in meta

            assert meta["schema.id"] == "14603317962659197404", "hash should be the same across tracers"
            assert meta["schema.type"] == "protobuf"
            json.loads(meta["schema.definition"])  # will throw if malformed
            assert "x-protobuf-number" in meta["schema.definition"]  # rough check that we register the protobuf numbers
            assert meta["schema.name"] == "proto_message.AddressBook"

            return True

        interfaces.library.validate_traces(request=self.serialization_response, validator=validator)
        interfaces.library.validate_traces(request=self.deserialization_response, validator=validator)
