from utils import context, irrelevant


@irrelevant("google_genai" not in context.weblog_variant)
class BaseGoogleGenaiTest: ...
