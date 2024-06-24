# WIP

## Add secrets

1. Install aws-cli
1. Save a valid github PATH token in a file named GH_TOKEN
1. Save a valid staging API key in a file named DD_API_KEY
1. then execute

```
aws-vault exec --debug build-stable-developer  # Enter a token from your MFA device
unset AWS_VAULT
cat DD_API_KEY | aws-vault exec build-stable-developer -- ci-secrets set ci.system-tests.dd_api_key
cat GH_TOKEN | aws-vault exec build-stable-developer -- ci-secrets set ci.system-tests.gh_token
```
