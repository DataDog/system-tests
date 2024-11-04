            curl -X POST https://dd-feature-parity-dev.azurewebsites.net/cijobreports \
              --fail
              --header "Content-Type: application/json" \
              --header "FP_API_KEY: ${FP_API_KEY}" \
              --data '{
  "context": "Nightly",
  "version": "TODO",
  "startTimestamp": "2024-10-29T18:03:39.432Z",
  "endTimestamp": "2024-10-29T18:03:39.432Z",
  "repository": "DataDog/system-tests",
  "htmlUrl": "string",
  "artifactName": "string",
  "artifactUrl": "string",
  "category": "Build",
  "status": "Started",
  "tags": {
    "additionalProp1": "string",
    "additionalProp2": "string",
    "additionalProp3": "string"
  }
}' \
              --include