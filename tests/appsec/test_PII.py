from utils import BaseTestCase, context, skipif


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
@skipif(context.library == "dotnet", reason="missing feature")
@skipif(context.library == "java", reason="missing feature")
class Test_Scrubbing(BaseTestCase):
    def test_basic(self):
        raise NotImplementedError
