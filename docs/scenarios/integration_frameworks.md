# Integration Frameworks Testing

Integration frameworks testing is a mix of parametric library testing with weblogs for coordinating framework installation (e.g. LLM client frameworks like OpenAI, or DB client frameworks like Postgres).

## Running the tests

```bash
./build.sh python
./run.sh INTEGRATION_FRAMEWORKS_OPENAI -L python --weblog openai-py@2.0.0 tests/integration_frameworks/llm/openai/test_openai_apm.py -vv
```

which will run the tests for all frameworks.

## Generating cassettes

To generate cassettes for a given framework, run the following command:

```bash
./utils/scripts/generate-integration-framework-cassettes.sh
```

which will run the tests without caring about the test assertions, and will enforce proper API keys to generate the cassettes one time.