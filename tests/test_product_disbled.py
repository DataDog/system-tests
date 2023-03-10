from utils import context, interfaces, missing_feature, bug, released, scenarios


@released(python="1.7.0", dotnet="2.12.0", java="0.108.1", nodejs="3.2.0")
@bug(context.uds_mode and context.library < "nodejs@3.7.0")
@missing_feature(library="cpp")
@missing_feature(library="ruby")
@missing_feature(library="php")
@missing_feature(library="golang", reason="Implemented but not merged in master")
class TestProductDisabled:
    @scenarios.telemetry_app_started_products_disabled
    def test_app_started_product_disabled(self):
        """Assert that product informations are not reported when products are disabled in telemetry"""

        telemetry_data = list(interfaces.library.get_telemetry_data())
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            if data["request"]["content"].get("request_type") == "app-started":
                content = data["request"]["content"]
                assert (
                    "products" not in content["payload"]
                ), "Product information is present telemetry data on app-started event when all products are diabled"
