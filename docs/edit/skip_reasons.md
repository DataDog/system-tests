Test can be skipped for several reason. Each reason is motivated, and has different effects on reports : 

* `Not relevant`: feature is not relevant in this context, and will never be implement in the agent. Test is not reported at all
* `todo tests`: feature is implemented in agent, but test must be implemented in system tests or [weblog](../edit/weblog.md). It can also means that the test is flaky, and must fixed on system tests' side
* `known bug`: feature is bugged or flaky. Please mention the JIRA ticket
* `missing feature`: not yet implemented in the agent, please mention the JIRA ticket if it exists

To mark a test with one of theese categories, use `skipif` decorator, and fill `reason` argument with it (you can append more details).

The skip condition can use library name and version, and even do some comparizon. Example:

```python
from utils import skipif


@skipif(context.library == "ruby", reason="known bug: ARB-123")
@skipif(context.library in ("python", "nodejs"), reason="not relevant")
@skipif(context.library == "java@4.28", reason="known bug: AJA-!@#")
@skipif(context.library < "dotnet@1.28.5", reason="Appsec WAF release: 1.28.5")
```
