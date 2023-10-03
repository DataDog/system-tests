!!! OBSOLETE, TO BE UPDATED WITH MANIFEST FILES

Once you have written the test, as you have not yet implemented the feature, you must declare that the test is expected to fail until a given version number. You must use the good manifest files:

```yaml
tests/:
  test_feature.py:
    Test_AwesomeFeature:
      "*": v1.2.3
      custom_weblog: missing_feature
```

It means that the test will be executed starting version `1.2.3` for all weblog, but `custom_weblog`. For `custom_weblog`, the test will be flagged as missing feature, which means it'll be executed, but ignored if failing, and reported as XPASS if it succeed.
