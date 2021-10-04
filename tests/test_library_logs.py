from utils import context, BaseTestCase, interfaces, skipif


class Test_NoExceptions(BaseTestCase):
    @skipif(context.library != "dotnet", reason="Not relevant: .NET logs are not in stdout")
    def test_dotnet(self):
        """There is not exception in dotnet-tracer-managed log files"""
        interfaces.library_dotnet_managed.assert_absence(r"[A-Za-z]+\.[A-Za-z]*Exception")
