## use `logger`

When a test fails, having the good information in the output makes all the difference. There is sweet spot between no info, and too much info, use your common sense!

```python
from utils import logger

...

logger.debug("Try to find span with ...")
logger.info("Found to find span with ...")
logger.error("Span is missing ...")
```
