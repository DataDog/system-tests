from utils import irrelevant, context


@irrelevant("anthropic" not in context.weblog_variant)
class BaseAnthropicTest: ...
