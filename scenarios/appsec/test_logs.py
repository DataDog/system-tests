from utils import BaseTestCase, context, skipif, interfaces

# get the default log outpu
stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed


@skipif(context.library == "cpp", reason="not relevant: No C++ appsec planned")
@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
class Test_Errors(BaseTestCase):
    """AppSec errors logs should be standardized"""

    @skipif(context.library == "dotnet", reason="known bug: ERROR io CRITICAL")  # and the last sentence is missing
    @skipif(context.library == "java", reason="known bug: ERROR io CRITICAL")
    def test_c04(self):
        """Log C4: Rules file is missing"""
        stdout.assert_presence(
            r'AppSec could not find the rules file in path "?/donotexists"?. '
            r"AppSec will not run any protections in this application. "
            r"No security activities will be collected.",
            level="CRITICAL",
        )
