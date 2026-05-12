# AI Tools prompt validation guide (beta)

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
├── 📁 .promptfoo/                       # Promptfoo test directory
│   ├── 📄 tests_overview.yaml          # Tests for general system-tests overview
│   ├── 📄 tests_aws_ssi.yaml           # Tests for AWS SSI scenarios
│   ├── 📄 tests_end_to_end.yaml        # Tests for end-to-end scenarios
│   ├── 📄 tests_activate_tests.yaml    # Tests for test activation/deactivation
│   └── 📄 tests_task_java_endpoint_prompt.yaml # Tests for Java endpoint tasks
└── 📁 utils/scripts/ai/                 # AI utility scripts
    └── 📄 promptfoo_eval.sh            # Interactive wizard for running evaluations
```

### Key Components

* **promptfooconfig.yaml**: Main configuration that orchestrates all test suites and configures the Claude AI provider
* **.promptfoo/**: Contains all test definitions organized by scenario type
* **Test files**: Each YAML file contains specific test cases for different system-tests scenarios
* **promptfoo_eval.sh**: Interactive wizard script for running evaluations from the terminal

## Running Promptfoo Evaluations

The system-tests repository uses an interactive wizard script that guides you through the evaluation process step by step.

### Prerequisites

Before running the wizard, ensure you have:

* **Promptfoo** installed (see installation instructions above)
* **Internet access** for the Claude AI provider

### Running the Wizard

From the repository root, execute:

```bash
./utils/scripts/ai/promptfoo_eval.sh
```

### Wizard Steps

The wizard guides you through three interactive steps:

#### Step 1: Select Provider

Choose which AI provider will generate and evaluate the test responses. The wizard automatically discovers available providers from `promptfooconfig.yaml`:

```
━━━ Step 1: Select Provider ━━━

Which provider would you like to use for the evaluation?

  0) Use ALL providers

  1) anthropic:claude-agent-sdk

Enter your choice (0-1):
```

**Note:** The default configuration uses the Claude AI Agent SDK provider, which provides the most comprehensive evaluation capabilities.

#### Step 2: Select Test Scenarios

Choose to run all scenarios or select a specific one. The wizard automatically discovers all available test files from the `.promptfoo/` directory:

```
━━━ Step 2: Select Test Scenarios ━━━

Would you like to run all scenarios or select specific ones?

  0) Run ALL scenarios

  1) activate_tests
  2) aws_ssi
  3) end_to_end
  4) k8s_tests
  5) overview
  6) task_java_endpoint_prompt

Enter your choice (0-6):
```

#### Step 3: Automatic Execution

The wizard then automatically executes `promptfoo eval` with the selected provider and test file(s).

### Example Output

```
╔═══════════════════════════════════════════════════════════╗
║          🤖 Promptfoo Evaluation Wizard 🧙‍♂️               ║
╚═══════════════════════════════════════════════════════════╝

━━━ Step 1: Select Provider ━━━
✓ Selected provider: anthropic:claude-agent-sdk

━━━ Step 2: Select Test Scenarios ━━━
✓ Selected scenario: aws_ssi

━━━ Step 3: Running Evaluation ━━━
📊 Running promptfoo evaluation...
✅ Evaluation complete!
```

### Reviewing Results

After the evaluation completes, view the results in the interactive web UI:

```bash
promptfoo view
```

## How Promptfoo Testing Works

Promptfoo evaluates AI assistant responses by:

1. **Test Definition**: Each YAML test file contains scenarios with `user_prompt` fields and expected behavior assertions
2. **Provider Execution**: The Claude AI provider receives each prompt and generates a response
3. **Assertion Validation**: Promptfoo validates responses against defined assertions (e.g., contains certain keywords, follows specific patterns, meets quality criteria)
4. **Results Reporting**: Detailed pass/fail results with explanations for each test case

This approach ensures:
* **Consistency**: AI responses remain accurate across documentation updates
* **Quality**: Responses meet defined quality standards
* **Regression Prevention**: Changes to rules or documentation don't break existing functionality