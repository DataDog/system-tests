Here is the workflow to review pull requests:

```mermaid
graph TD
    Commit[Commit] --> CI
    CI[All CI jobs are green?] -->|Yes| Content
    Content[What's in the PR?] -->|Version declaration <sup>1</sup>| Version
    Content -->|New test method <sup>2</sup>| PHP
    Content -->|New test class <sup>3</sup>| Naming
    Content -->|Other <sup>4</sup>| NewMisc
    Version -->|Version == Prod| Go
    Version[What is this version?] -->|Version < Prod| LocalTest
    Version -->|Prod < Version <= Dev| WhichLanguage
    Version -->|Dev < Version| Nogo
    LocalTest[Do a local test<sup>5</sup>] --> Go
    WhichLanguage[What is the language?] -->|PHP| LocalTest
    WhichLanguage -->|Others| Go
    Naming[Naming is coherent and not redundant?] --> Released
    Released[Released decorator for all languages?] --> Coverage
    Coverage[Coverage decorator?] --> RFC
    RFC[RFC decorator?] --> PHP
    PHP[PHP is enabled] --> |yes| LocalTest2
    PHP --> |no| Go
    LocalTest2[Do a local test with PHP/dev<sup>5</sup>] --> Go
    NewMisc[Good luck !]
```

## Notes

1. Manifest files allows to declare at which version of a component a feature is supposed to be working. In consequence, it enable the underlying tests. We must ensure that this change is correctly tested, otherwise it may break some CIs. [Example](https://github.com/DataDog/system-tests/commit/a1970be4ffb3176fa71135a2feb302311be88baa)
1. A new test method is added in an existing test class.
1. A new test class is added.
1. Any other change, it'll require a more complete review that can't be sumerize in a simple workflow
1. PHP CI is not public (ie, it require authentication to get artifacts). As system-tests repo is public, we cannot ship autnentication token in our CI. In consequences, any change that implies the dev version of the PHP library must be tested locally.
