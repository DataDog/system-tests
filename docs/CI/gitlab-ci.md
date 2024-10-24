# WIP

## Add secrets

1. Install aws-cli
2. Save a valid github PATH token in a file named GH_TOKEN
3. then execute

```
aws-vault exec --debug build-stable-developer  # Enter a token from your MFA device
unset AWS_VAULT
cat GH_TOKEN | aws-vault exec build-stable-developer -- ci-secrets set ci.system-tests.gh_token
```
