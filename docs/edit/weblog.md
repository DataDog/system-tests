A weblog is a simple HTTP application that ships a datadog library, and expose some endpoints. All weblog should have the same interface:

- `/`
- `/waf` => accepts all methods, all content-type, all sub path
