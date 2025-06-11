# AI Tools prompt validation guide

The selected tool for validating and ensuring that our AI assistants correctly execute tasks requested by users is Promptfoo. This framework enables systematic testing, ensuring high-quality responses, prompt accuracy, and consistent performance across various user interactions.

Promptfoo is a testing framework designed specifically for evaluating and comparing prompts and outputs from AI language models. Its primary purpose is to help developers and researchers:

* Automate prompt evaluations: Run batches of tests with different inputs and compare outputs systematically.
* Optimize prompts: Easily iterate and refine prompts based on detailed feedback and metrics.
* Ensure quality: Maintain consistency, accuracy, and reliability of AI-generated responses through structured testing.

Promptfoo supports integration with multiple language models and allows testing across various prompt variants, aiding teams in efficiently developing robust, high-quality prompts for AI-driven applications.

**Validation tasks are not integrated into the Continuous Integration (CI) pipeline; instead, they'll be performed by users themselves in a semi-automated manner directly through the IDE, facilitating quick feedback and enhanced accuracy.**

## Installing Promptfoo (using Homebrew)

Install `promptfoo` easily using Homebrew:

```bash
brew install promptfoo
```

Verify the installation:

```bash
promptfoo --version
```

For more information, visit the [official Promptfoo documentation](https://www.promptfoo.dev/docs/getting-started/).

## Promptfoo - system-tests structure

system-tests/
├── 📄 promptfooconfig.yaml             # Main configuration file
├── 📄 promptfoo-errors.log             # Error logs
└── 📁 .promptfoo/                      # Promptfoo test directory
├── 📄 local_cursor_provider.py     # Custom provider for Cursor IDE integration
├── 📄 tests_overview.yaml          # Tests for general system-tests overview
├── 📄 tests_aws_ssi.yaml           # Tests for AWS SSI scenarios
├── 📄 tests_end_to_end.yaml        # Tests for end-to-end scenarios
├── 📄 tests_activate_tests.yaml    # Tests for test activation/deactivation

### Key Components

* **promptfooconfig.yaml**: Main configuration that orchestrates all test suites
* **.promptfoo/**: Contains all test definitions organized by scenario type
* **local_cursor_provider.py**: Custom provider for IDE integration (133 lines)
* **Test files**: Each YAML file contains specific test cases for different system-tests scenarios

## Run the tests inside the IDE

We execute the tests in three simple steps:

1. **Generate Test Responses:**
   Ask Cursor AI to parse your test files and respond to questions. Ensure it doesn't modify any code, but instead, instruct it to write the intended responses and actions into a dedicated results file.
2. **Evaluate Responses:**
   Run an evaluation of these responses by parsing the results file using a customized Promptfoo provider implementation.
3. **Review Results:**
   Visualize and analyze the test outcomes clearly and effectively.

### Generate Test Responses

To run the full test suite, ask in the chat (agent mode):

```
Delete the logs/responses.yaml file if exists. Parse the yaml file "promptfooconfig.yaml" and extract all the tests files. Parse these tests yaml files one by one and read the value of the field user_prompt and answer the questions or perform the action.  All the actions that you perform MUST NOT require interact with the user. NEVER edit files EXCEPT the "responses.yaml", only print the proposed changes. NEVER launch shell command, only print the proposed command. you MUST ALWAYS create or update and write in other yaml file called "responses.yaml" in the "logs" folder the query (create prompt field) and the associated response you provided (output), under the root node "responses".

```

if you want to run only for one test suite, for example the "aws ssi":

```
Delete the logs/responses.yaml file if exists. Parse ONLY the file .promptfoo/tests_aws_ssi.yaml and read the value of the field user_prompt  and answer the questions or perform the action.  All the actions that you perform MUST NOT require interact with the user. NEVER edit files EXCEPT the "responses.yaml", only print the proposed changes. NEVER launch shell command, only print the proposed command. you MUST ALWAYS create and write in other yaml file called "responses.yaml" in the "logs" folder the query (create prompt field) and the associated response you provided (output), under the root node "responses".

```
### Evaluate Responses

Once you've generated the logs/responses.txt file, you're ready to run the Promptfoo evaluation to assess the accuracy and quality of your assistant’s responses.

```bash
promptfoo eval
```

Or if you want to evaluate only one test suite:

```bash
promptfoo eval -t .promptfoo/tests_aws_ssi.yaml
```

### Review Results

```bash
promptfoo view
```