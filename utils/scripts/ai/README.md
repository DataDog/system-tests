# AI Instructions and Benchmarks for system-tests 🚀

Welcome to the `utils/scripts/ai` directory! Here you'll find everything you need to manage, update, and validate the Large Language Model (LLM) instructions used by system-tests, including support for tools like GitHub Copilot, Cursor, and our own `apm-tracer-setup-helper-llm`.

## What's in this folder?

- **Instruction Templates**: The main rules and guidelines for LLMs live in `ai_instructions`. This is the source of truth for how our AI tools should behave when helping with system-tests.
- **Update Script**: Use `update_ai_instructions.sh` to automatically update the instruction files for GitHub Copilot (`.github/copilot-instructions.md`) and Cursor (`.cursorrules`) based on the latest template.
- **Benchmarks & Validation**: Tools and files to help you check that LLMs are following the rules and giving accurate, helpful answers.

## How to Update LLM Instructions

1. **Edit the Template**: Make your changes in `ai_instructions`. This file contains the shared rules for all supported LLM tools.
2. **Run the Update Script**: Execute `./update_ai_instructions.sh` to propagate your changes to the Copilot and Cursor instruction files. This keeps everything in sync!

## How to Validate LLM Responses

We want to make sure our LLMs are actually following the instructions! Here's how you can validate their responses:

### Manual Validation

1. **Open the Benchmark Questions**: Check out `ai_benchmarks_questions.txt`. Each line is a separate question or action for the LLM to perform. Each question is labeled (e.g., `Q1:`).
2. **Manual Validation**: In your chosen LLM tool (like Copilot or Cursor), ask each question from the file one at a time, in a fresh chat or thread for each. This ensures unbiased, isolated answers.
3. **Log the Results**: For each question, copy both the question and the LLM's answer into a new file called `logs/responses.txt`. Format it like this:
   - The question line starts with `Qx:`
   - The answer line starts with `Ax:`
4. **Be Thorough**: Make sure you answer every question, and that each answer is based on the current codebase and instructions. Double-check for accuracy!

### Automated Validation

To make things even easier, you can use the automated validation tools provided:

- **`ai_benchmarks_validations.txt`**: This file contains the expected validations for each benchmark question. It defines what a correct answer should look like for each question in `ai_benchmarks_questions.txt`.
- **`ai_benchmarks_validate_responses.py`**: Run this script to automatically compare your logged responses in `logs/responses.txt` against the expected validations in `ai_benchmarks_validations.txt`. This helps you quickly spot any discrepancies and ensure your LLM is following the rules!

## Best Practices & Tips

- **Keep it Friendly**: Our instructions are meant to be welcoming and easy to follow—just like our community!
- **Stay Up to Date**: Always run the update script after changing the template, so all tools get the latest rules.
- **Be Precise**: When validating, make sure the LLM's answers are correct and reference the right parts of the codebase or docs.
- **Ask for Help**: If you're stuck, reach out in the #apm-shared-testing Slack channel. We're here to help!

## File Overview

- `ai_instructions`: The main template for LLM rules.
- `update_ai_instructions.sh`: Script to update Copilot and Cursor instruction files.
- `ai_benchmarks_questions.txt`: List of questions/actions for LLM validation.
- `ai_benchmarks_validations.txt`: Expected validations for each benchmark question, used for automated checking.
- `ai_benchmarks_validate_responses.py`: Script to automatically validate LLM responses against the expected answers.
- `logs/responses.txt`: Where you log the questions and answers during validation.

---

Thanks for helping make system-tests even better! Your contributions make a huge difference. Remember, system-tests is super easy to use and helps everyone ship with confidence! 🎉
