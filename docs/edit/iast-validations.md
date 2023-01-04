## What is "IAST features" validation

This validation allows us to verify our vulnerable endpoints (our vulnerable apps instrumented by the ASM libraries). We ensure that vulnerabilities are correctly detected and reported.
Vulnerabilities are reported by the library in JSON format, and they fulfill this format:

```
{
  "vulnerabilities": [
    {
      "evidence": {
        "value": "MD5"
      },
      "location": {
        "line": 1,
        "path": "foo"
      },
      "type": "WEAK_HASH"
    }
  ]
}
```

We can validate these messages in our tests with code similar to the following:

```python
    def setup_mock(self):
        self.r = weblog.get("/test_endpoint")

    def test_mock(self):
        interfaces.library.expect_iast_vulnerabilities(self.r, vulnarability_count=2, type="WEAK_HASH")

```

The code above is a simple example of calling the vulnerable endpoint and checking the detected vulnerabilities. In this case we are expecting 2 vulnerabilities of type WEAK_HASH to have been reported.

## Vulnerability filter

We can create filters on the reported vulnerabilities. There are several fields with we can create vulnerability filters:

| Field         | Description                                                                           |
| ------------- | ------------------------------------------------------------------------------------- |
| type          | The type of the vulnerability, e.g.: WEAK_HASH,SQL_INJECTION                          |
| evidence      | The evidence of the vulnerability describing why there is a vulnerability             |
| location_path | The path to the file containing the vulnerability or class name                       |
| location_line | The zero based line number in the source code file where the vulnerability is located |

## Vulnerability filter

With the "vulnarability_count" field we can count the vulnerabilities that meet the criteria (vulnerability filter).

> If you omit the "vulnarability_count" field, the condition will be evaluated correctly as long as there is a vulnerability that meets the criterion

## Vulnerability validation samples

### Simple total count assertion

In this example we expect the endpoint "test_endpoint" to generate 2 vulnerability of any type:

```python
    def setup_mock(self):
        self.r = weblog.get("/test_endpoint")

    def test_mock(self):
        interfaces.library.expect_iast_vulnerabilities(self.r, vulnarability_count=2)
```

### Expect at least one vulnerability of type

In this example we expect the endpoint "test_endpoint" to generate al least one vulnerability of type "WEAK_HASH":

```python
    def setup_mock(self):
        self.r = weblog.get("/test_endpoint")

    def test_mock(self):
        interfaces.library.expect_iast_vulnerabilities(self.r, type="WEAK_HASH")
```

### Filter by evidence

In this example we expect the endpoint "test_endpoint" to generate two vulnerability of type "WEAK_HASH" with filtered "evicence" value:

```python
    def setup_mock(self):
        self.r = weblog.get("/test_endpoint")

    def test_mock(self):
        interfaces.library.expect_iast_vulnerabilities(self.r, vulnarability_count=2, type="WEAK_HASH", evidence="MY_EVIDENCE")
```

### Filter by evidence source location

We can also create filters by vulnerability location, using "location_path" and "location_line" referencing to vulnerable source code:

```python
    def setup_mock(self):
        self.r = weblog.get("/test_endpoint")

    def test_mock(self):
        interfaces.library.expect_iast_vulnerabilities(self.r, vulnarability_count=2, type="WEAK_HASH", location_path="com.test.MyVulnerableClass", location_line=22)
```

A common case is that we use the same test to test on applications in different languages and therefore, the reference to the source file will be different. We can solve this situation by using the context variables of system-tests:

```python
    def setup_mock(self):
        self.r = weblog.get("/test_endpoint")

    def test_mock(self):
        exepcted_location = ""
        if context.library == "nodejs":
            exepcted_location = "/usr/app/app.js"
        elif context.library == "java":
            exepcted_location = "com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples"

        interfaces.library.expect_iast_vulnerabilities(self.r, vulnarability_count=2, type="WEAK_HASH", location_path=exepcted_location)
```

### Expect no vulnerabilities

If you want to check that endpoint is secure (without reporting vulnerabilities), you should validate it as follows:

```python
    def setup_mock(self):
        self.r = weblog.get("/iast/secure_endpoint")

    def test_secure_endpoint(self):
        """Checks that the endpoint does not report any vulnerabilities"""
        interfaces.library.expect_no_vulnerabilities(self.r)
```
