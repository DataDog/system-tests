DD_API_KEY=$(pulumi config get ddagent:apiKey)
sed -i '' "s/MY_DD_API_KEY/$DD_API_KEY/g" autoinjection/ansible/datadog_playbook.yml