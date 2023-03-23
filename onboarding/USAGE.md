
## Run script usage

This is an example of a test launch with the minimal mandatory parameters:

`./run.sh --KeyPairName mykeypair --subnet subnet-zzzz --vpc sg-12345,sg-6789 --private-key-path /Users/user/mykeypair.pem --instance-type t2.micro`

The mandatory parameters are:

- **--KeyPairName:** Key pair name. See [Amazon EC2 Key pair](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)
- **--subnet:** AWS subnet id
- **--vpc:** AWS VPC groups id (separated by comma)
- **--private-key-path:** Path to your local perm file. See [AWS create key pairs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-key-pairs.html)
- **--instance-type:** Type of Amazon EC2 instance. See [AWS EC2 Instance Types](https://aws.amazon.com/ec2/instance-types/)

The optional parameter is:

- **--dd-site:** Datadog backend url (example datadoghq.com)

> Don't forget to specify the DD_API_KEY and DD_APP_KEY using Pulumi secrets

You can filter the tests by scenario, language, OS distribution, environment or weblog name. These are the filtering options:

- **--filter-provision-scenario:** The injection of libraries can take place in three scenarios, each of which is represented by the values:
  - **host:** Datadog Agent and your application deployed on the same host.
  - **host_docker:** Datadog Agent installed on host and your application deployed on container.
  - **docker:** Datadog Agent and your application installed on containers.
- **--filter-language:** Run only the tests associated with a language (java, nodejs, dotnet).
- **--filter-os-distro:** Run the tests on the specified machine type.
- **--filter-env:** Run the tests with Datadog releases or snapshots (prod or dev).
- **--filter-weblog:** Run the tests on a specific application/weblog.

This is an example of a test launch with the mandatory parameters and filtered by scenario and language:

`./run.sh --KeyPairName mykeypair --subnet subnet-zzzz --vpc sg-12345,sg-6789 --private-key-path /Users/user/mykeypair.pem --instance-type t2.micro --filter-provision-scenario docker --filter-language java`

> By default, if no scenario is specified, the "Agent and application on host" scenario will be executed.