## What is "IAST features" validation?

With this type of validation we can verify that our vulnerable endpoints (our vulnerable apps instrumented by the ASM libraries) correctly detect and report the expected vulnerabilities.
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

```
    def test_insecure_hashing_all(self):
        """Test insecure hashing all algorithms"""

        # Call to vulnerable endpoint
        r = self.weblog_get("/iast/insecure_hashing")

        # Check library received IAST messages
        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator()
            .expect_only_these_vulnerabilities(4)
            .with_data(
                Vulnerability(
                    type="WEAK_HASH"
                )
            )
            .validate,
        )
```
The code above is a simple example of calling the vulnerable endpoint and checking the detected vulnerabilities. In this case we are expecting 4 vulnerabilities of type WEAK_HASH to have been reported. 

The following sections show the details of this validation API to build more complex conditions.

## Expected counter

We have 4 methods that allow us to create expected vulnerability count conditions. These methods will normally be accompanied by vulnerability filtering as explained in the next sections:

* `expect_exact_count` - This method receives as a parameter the number of vulnerabilities expected after applying the filter if exists (see vulnerability filter section).
* `expect_at_least_count` - This method receives as parameter the least number of vulnerabilities expected for a request (after applying the filter if it exists).
* `expect_any_match` - Conditions on the existence of a vulnerability 
* `expect_only_these_vulnerabilities` - Special method that checks that the number of leaked vulnerabilities is the same as the total number of reported vulnerabilities (you can check it clearly in the examples section).

## Vulnerability filter

We can use the vulnerability class to create filters on the reported vulnerabilities. The class we use to create the filter has the following fields:

```
class Vulnerability:
    def __init__(
        self,
        type=None,
        location_path=None,
        location_line=None,
        evidence_value=None,
    ):
        self.type = type
        self.location_path = location_path
        self.location_line = location_line
        self.evidence_value = evidence_value
```

We use the method `with_data` with the above class to create filters:

```
    def test_insecure_hashing_sha1(self):
        """Test insecure hashing sha1 algorithm"""
        r = self.weblog_get("/iast/insecure_hashing?algorithmName=sha1")

        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator()
            .expect_exact_count(1)
            .with_data(
                Vulnerability(
                    type="WEAK_HASH",
                    location_path="com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples",
                    location_line=33,
                    evidence_value="SHA-1",
                )
            )
            .validate,
        )
```
In the above example we are expecting the called endpoint to have reported 1 vulnerability of type "WEAK_HASH" detected in the source file "CryptoExamples" (line 33) with the evidence "SHA-1"

## IAST Validations by examples

This section shows some examples in the IAST validation options.

### Check all vulnerability count without any filter

The next sample shows you how to check all reported vulnerabilities. 

```
interfaces.library.add_appsec_iast_validation(
    r, VulnerabilityValidator().expect_only_these_vulnerabilities(2).validate
)
```
In this case, the above behaviour is the same as the following code:

```
interfaces.library.add_appsec_iast_validation(
    r, VulnerabilityValidator().expect_exact_count(2).validate
)
```
The following JSON represents a valid message for the above validation:

```
{
   "vulnerabilities":[
      {
         "evidence":{
            "value":"MD5"
         },
         "location":{
            "line":33,
            "path":"CryptoExamples"
         },
         "type":"WEAK_HASH"
      },
      {
         "evidence":{
            "value":"INSERT"
         },
         "location":{
            "line":11,
            "path":"MyDao"
         },
         "type":"SQL_INJECTION"
      }
   ]
}
```

### Exact count and expected only vulnerabilities

The next sample checks that 2 vulnerabilities of type "WEAK_HASH" has been reported:

```
interfaces.library.add_appsec_iast_validation(
    r,
    VulnerabilityValidator()
        .expect_exact_count(2)
         .with_data(
            Vulnerability(
                type="WEAK_HASH"
            )
        )
        .validate,
 )
```
The following JSON represents a compliant message for the above validation:

```
{
   "vulnerabilities":[
      {
         "evidence":{
            "value":"MD5"
         },
         "location":{
            "line":33,
            "path":"CryptoExamples"
         },
         "type":"WEAK_HASH"
      },
      {
         "evidence":{
            "value":"MD4"
         },
         "location":{
            "line":14,
            "path":"CryptoExamplesMd4"
         },
         "type":"WEAK_HASH"
      },
      {
         "evidence":{
            "value":"INSERT"
         },
         "location":{
            "line":11,
            "path":"MyDao"
         },
         "type":"SQL_INJECTION"
      }
   ]
}
```
On the other hand, the previous message will NOT be valid for the following validation:

```
interfaces.library.add_appsec_iast_validation(
    r,
    VulnerabilityValidator()
        .expect_only_these_vulnerabilities(2)
         .with_data(
            Vulnerability(
                type="WEAK_HASH"
            )
        )
        .validate,
 )
```
The above code states that in total only 2 vulnerabilities of type "WEAK_HASH" should have been reported.

Parameter for `expect_only_these_vulnerabilities` is optional:

```
#We expect only vulnerabilities of type "WEAK_HASH" (could be one vulnerability or many ). 
interfaces.library.add_appsec_iast_validation(
    r,
    VulnerabilityValidator()
        .expect_only_these_vulnerabilities()
         .with_data(
            Vulnerability(
                type="WEAK_HASH"
            )
        )
        .validate,
 )
```

```
#We expect only vulnerabilities in the file "InsecureCode" (could be one vulnerability or many ) 
interfaces.library.add_appsec_iast_validation(
    r,
    VulnerabilityValidator()
        .expect_only_these_vulnerabilities()
         .with_data(
            Vulnerability(
               location_path="InsecureCode",
            )
        )
        .validate,
 )
```
### Other simple samples
```
    def test_insecure_hashing_sha1(self):
        """Test insecure hashing sha1 algorithm"""
        r = self.weblog_get("/iast/insecure_hashing?algorithmName=sha1")
        interfaces.library.assert_trace_exists(r)
        
        #Expect one vulnerability with all criteria
        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator()
            .expect_exact_count(1)
            .with_data(
                Vulnerability(
                    type="WEAK_HASH",
                    location_path="com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples",
                    location_line=33,
                    evidence_value="SHA-1",
                )
            )
            .validate,
        )
```

```
    def test_insecure_hashing_sha1(self):
        """Test insecure hashing sha1 algorithm"""
        r = self.weblog_get("/iast/insecure_hashing?algorithmName=sha1")
        interfaces.library.assert_trace_exists(r)
        
        #Expect at least 3 vulnerabilities with all criteria
        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator()
            .expect_at_least_count(3)
            .with_data(
                Vulnerability(
                    type="WEAK_HASH",
                    location_path="com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples",
                    location_line=33,
                    evidence_value="SHA-1",
                )
            )
            .validate,
        )
```

```
    def test_insecure_hashing_sha1(self):
        """Test insecure hashing sha1 algorithm"""
        r = self.weblog_get("/iast/insecure_hashing?algorithmName=sha1")
        interfaces.library.assert_trace_exists(r)
        
        #Expect at least 1 vulnerability of type "WEAK_HASH"
        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator()
            .expect_any_match()
            .with_data(
                Vulnerability(
                    type="WEAK_HASH"
                )
            )
            .validate,
        )
```


### Multiple validations

We can use more than one validations for a unique endpoint. 
For example, if we have the endpoint "test/iast" and the following JSON response:

```
{
   "vulnerabilities":[
      {
         "evidence":{
            "value":"MD5"
         },
         "location":{
            "line":33,
            "path":"CryptoExamples"
         },
         "type":"WEAK_HASH"
      },
      {
         "evidence":{
            "value":"testEvidence"
         },
         "location":{
            "line":24,
            "path":"PathTraversalExample"
         },
         "type":"PATH_TRAVERSAL"
      },
      {
         "evidence":{
            "value":"INSERT"
         },
         "location":{
            "line":11,
            "path":"MyDao"
         },
         "type":"SQL_INJECTION"
      }
   ]
}
```
We could validate full response with the following code:

```
    def test_example(self):
        r = self.weblog_get("/test/iast")
        
        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator().expect_only_these_vulnerabilities(3).validate,
        )

        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator()
            .expect_exact_count(1)
            .with_data(
                Vulnerability(
                    type="WEAK_HASH"
                )
            )
            .validate,
        )

        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator()
            .expect_any_match()
            .with_data(
                Vulnerability(
                    type="SQL_INJECTION"
                )
            )
            .validate,
        )

        interfaces.library.add_appsec_iast_validation(
            r,
            VulnerabilityValidator()
            .expect_at_least_count(1)
            .with_data(
                Vulnerability(
                    location_path="PathTraversalExample",
                    location_line=23
                )
            )
            .validate,
        )
```