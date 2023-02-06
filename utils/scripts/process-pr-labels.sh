echo "PULL_REQUEST_DRAFT: $PULL_REQUEST_DRAFT"

#Use github API in order to query for existing labels in this PR. 
PR_NUMBER=$(echo $GITHUB_REF | awk 'BEGIN { FS = "/" } ; { print $3 }')
echo "Working PR number: $PR_NUMBER"  
#Only if we are in PR (number)
if [ -n "$PR_NUMBER" ] && [ "$PR_NUMBER" -eq "$PR_NUMBER" ] 2>/dev/null; then
    existing_labels=$(curl \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        https://api.github.com/repos/datadog/system-tests/issues/$PR_NUMBER/labels| jq -r '.[]|select(.name | startswith("test_")).name| @sh')
    existing_labels=($existing_labels)
fi
echo "Number of tests labels found: " ${#existing_labels[@]}
echo "Test labels: "${existing_labels[@]}

#Load json file with all libraries
jsonExclusion="$(cat .github/workflows/library_langs.json)"

#We have a json with all library names for exclusion. We remove from exclusion the found labels          
for label_pr in "${existing_labels[@]}"
do
    label_pr=$(echo $label_pr|tr -d "'"|tr -d "test_") #Remove quotes and prefix
    jsonExclusion=$(echo $jsonExclusion|jq --arg labelpr "$label_pr" 'del(.[] | select(.variant.library == $labelpr))')
done

#If we have label "test_all" we are going to execute full matrix
#If we have PR in "Ready to review" we are going to execute full matrix 
if [[ " ${existing_labels[*]} " =~ "test_all" || "$PULL_REQUEST_DRAFT" != "true" ]]; then
    jsonExclusion=$(echo $jsonExclusion|jq 'del(.[] )')
fi

#Print exclusion and return
echo $jsonExclusion| jq -r tostring
echo "library=$(echo $jsonExclusion| jq -r tostring)" >> $GITHUB_OUTPUT