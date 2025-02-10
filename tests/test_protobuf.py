from utils import weblog, interfaces, scenarios, irrelevant, context, bug, features, missing_feature, flaky
from utils.tools import logger


class Test_Protobuf:

    def setup_protobuf(self):
        self.serialization_response = weblog.get("/protobuf/serialize")
        self.deserialization_response = weblog.get(f"/protobuf/deserialize?msg={self.serialization_response.text}")

    # @irrelevant(context.library in ["java", "dotnet"], reason="New behavior with cluster id not merged yet.")
    def test_protobuf(self):
        assert self.serialization_response.status_code == 200, self.serialization_response.text
        assert self.deserialization_response.status_code == 200, self.deserialization_response.text

        def validator(span):
            meta = span.get("meta", {})
           # TODO

            return True

        interfaces.library.validate_spans(request=self.serialization_response, validator=validator)
        interfaces.library.validate_spans(request=self.deserialization_response, validator=validator)
