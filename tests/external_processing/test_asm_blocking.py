from utils import scenarios, features, irrelevant
from tests.appsec import test_request_blocking as base_request_blocking
from tests.appsec import test_blocking_addresses as base_blocking_addresses


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_AppSecRequestBlocking(base_request_blocking.Test_AppSecRequestBlocking):
    pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_client_ip(base_blocking_addresses.Test_Blocking_client_ip):
    pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_request_method(base_blocking_addresses.Test_Blocking_request_method):
    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_blocking_before(self):
        pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_request_uri(base_blocking_addresses.Test_Blocking_request_uri):
    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_blocking_before(self):
        pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_request_path_params(
    base_blocking_addresses.Test_Blocking_request_path_params
):
    @irrelevant(True, reason="The endpoint /param is not implemented in the weblog")
    def test_blocking(self):
        pass

    @irrelevant(True, reason="The endpoint /param is not implemented in the weblog")
    def test_blocking_before(self):
        pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_request_query(base_blocking_addresses.Test_Blocking_request_query):
    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_blocking_before(self):
        pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_request_headers(base_blocking_addresses.Test_Blocking_request_headers):
    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_blocking_before(self):
        pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_request_cookies(base_blocking_addresses.Test_Blocking_request_cookies):
    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_blocking_before(self):
        pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_response_status(base_blocking_addresses.Test_Blocking_response_status):
    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_blocking(self):
        pass

    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_non_blocking(self):
        pass

    @irrelevant(True, reason="The endpoint /finger_print is not implemented in the weblog")
    def test_not_found(self):
        pass


@features.not_reported
@scenarios.external_processing_blocking
class Test_ExternalProcessing_ASM_Blocking_response_headers(base_blocking_addresses.Test_Blocking_response_headers):
    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_blocking(self):
        pass

    @irrelevant(True, reason="The endpoint /tag_value is not implemented in the weblog")
    def test_non_blocking(self):
        pass
