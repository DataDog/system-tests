# Lambda Testing scenario

The Lambda scenario is a variation on the [classical architecture](../architecture/overview.md#what-are-the-components-of-a-running-test) of the system-tests tailored to evaluate the `AWS Lambda` variants of the tracers when used to serve HTTP requests.

To achieve this we simulate the following AWS deployment architecture inside the system-tests using AWS provided tools :

```mermaid
graph LR
    A[Incoming HTTP Request] -->|HTTP| B[AWS Managed Load Balancer]
    B -->|event: request as JSON| C[AWS Lambda]
```

The AWS Managed Load Balancer could be any of the following ones:
- API Gateway
- Application Load Balancer
- Lambda function url service

To do this, we rely on two tools from AWS to emulate Lambda and Load Balancers:
- [AWS Lambda Runtime Interface Emulator](https://github.com/aws/aws-lambda-runtime-interface-emulator)
- [AWS SAM cli](https://github.com/aws/aws-sam-cli)

>Note: for now only the python variant ([`datadog_lambda`](https://github.com/DataDog/datadog-lambda-python)) is being tested simulating an `API Gateway`

## Key differences with end to end scenarios

To replace the **AWS Managed Load Balancer**, we run a dedicated container in front of the weblog named **Lambda Proxy**. It is responsible for converting the incoming request to a *lambda event* representation, invoking the lambda function running inside the weblog and converting back the return value of function to an http response.

The **Lambda Function** runs inside the **Weblog Container** thanks to the *AWS Lambda Runtime Interface Emumlator*.


There is no **Agent Container**, the **Datadog Extension** (equivalent to the  **Datadog Agent** in the context of lambda) needs to run inside the **Weblog Container**, the [**Application Proxy Container**](../architecture/overview.md#application-proxy-container) therefore needs to send traces back to the **Weblog Container**.


```mermaid
flowchart TD
    TESTS[Tests Container] -->|Send Requests| LambdaProxy
    LambdaProxy[Lambda Proxy] -->|Send Lambda Event| Application
    subgraph APP[Application Container]
        Extension[Extension *:8126]
        Application[Application *:8080]
    end
    Application --> | Send Traces | APPPROXY
    APPPROXY[Application Proxy] --> | Send back traces | Extension
    APPPROXY -->|mitmdump| TESTS
    Extension --> AGENTPROXY
    AGENTPROXY[Agent Proxy] -->|remote request| BACKEND
    AGENTPROXY -->|mitmdump| TESTS
    BACKEND[Datadog] -->|trace API| TESTS
```
