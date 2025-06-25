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

```
system-tests/
├── 📄 promptfooconfig.yaml              # Main configuration file
├── 📄 promptfoo-errors.log             # Error logs
├── 📁 .cursor/rules/                    # Cursor IDE rules directory
│   └── 📄 promptfoo-llm.mdc            # Rules file for automated test execution
└── 📁 .promptfoo/                       # Promptfoo test directory
    ├── 📄 local_cursor_provider.py     # Custom provider for Cursor IDE integration
    ├── 📄 tests_overview.yaml          # Tests for general system-tests overview
    ├── 📄 tests_aws_ssi.yaml           # Tests for AWS SSI scenarios
    ├── 📄 tests_end_to_end.yaml        # Tests for end-to-end scenarios
    ├── 📄 tests_activate_tests.yaml    # Tests for test activation/deactivation
    └── 📄 tests_task_java_endpoint_prompt.yaml # Tests for Java endpoint tasks
```

### Key Components

* **promptfooconfig.yaml**: Main configuration that orchestrates all test suites
* **.cursor/rules/promptfoo-llm.mdc**: Rules file that automates the test execution process in Cursor IDE
* **.promptfoo/**: Contains all test definitions organized by scenario type
* **local_cursor_provider.py**: Custom provider for IDE integration
* **Test files**: Each YAML file contains specific test cases for different system-tests scenarios

## Run the tests inside the IDE

The process has been simplified using the new rules file (`.cursor/rules/promptfoo-llm.mdc`) that provides automated instructions to the AI assistant. You can now execute tests in two simple steps:

### Generate Test Responses

**For the full test suite**, simply ask in the chat:

```
@promptfoo-llm.mdc Run the complete test suite.
```

**For a specific test suite**, reference the specific test file:

```
@promptfoo-llm.mdc test the file .promptfoo/tests_aws_ssi.yaml
```

The AI assistant will automatically:
1. Delete any existing `logs/responses.yaml` file
2. Parse the specified test files (or all test files if none specified)
3. Process each `user_prompt` field and generate responses
4. Create a `logs/responses.yaml` file with all query-response pairs
5. Remind you to run the evaluation command

### Evaluate Responses

Once the AI assistant has generated the `logs/responses.yaml` file, run the Promptfoo evaluation:

**For the full test suite:**
```bash
promptfoo eval
```

**For a specific test suite:**
```bash
promptfoo eval -t .promptfoo/tests_aws_ssi.yaml
```

### Review Results

```bash
promptfoo view
```

## Rules File Integration

The new approach leverages Cursor IDE's rules system through the `.cursor/rules/promptfoo-llm.mdc` file, which:

* Provides standardized instructions for test execution
* Eliminates the need for manual prompt construction
* Ensures consistent behavior across different test runs
* Supports both full test suite and individual test file execution
* Automatically handles file cleanup and response generation

This streamlined process makes it easier to validate AI assistant behavior and maintain high-quality responses across all system-tests scenarios.