# AI Tools Integration Guide

## Overview

The `system-tests` repository includes built-in AI integration capabilities designed to enhance developer productivity when implementing new tests, troubleshooting issues, and working with complex testing scenarios. These tools leverage comprehensive context about the repository structure, testing patterns, and best practices to provide intelligent assistance.

Knowledge of AI tools is drawn from the project's documentation (found in the docs directory), the source code itself, and predefined rules and instructions (.cursor/rules). Users are strongly encouraged to actively participate in continuous improvement efforts and contribute new capabilities to enhance the AI tools' functionality and effectiveness.

The default and recommended AI tool for developing with system-tests is Cursor AI, although using alternative tools is also fully supported and encouraged.

## The AI tools

### Github Copilot support

The predefined rules within the `system-tests` repository are optimized specifically for **Cursor AI**, but you can effortlessly adapt them for **GitHub Copilot** using Copilot itself.

To adapt rules for GitHub Copilot:

1. Activate Copilot's **Agent Mode**.
2. Open the Copilot chat and input the following instruction:

   ```
   Parse all files within the .cursor/rules directory, combine their contents into a single new file at .github/copilot-instructions.md, and remove any occurrences of the text:
    ---
    description:
    globs:
    alwaysApply:
    ---
   ```

**Important Reminders:**

* Do not commit the `.github/copilot-instructions.md` file.
* To add new rules or instructions, always use Cursor AI’s standard rule files located at ".cursor/rules"
* If you introduce new instructions or modify existing documentation, always include new tests. These tests are essential for validating the impact and effectiveness of your changes on the AI assistant’s functionality. Please refer to section [Prompt validation](ai-tools-prompt-validation.md) to know about the ai prompt validations.

### Cursor

Cursor AI is the default IDE and automatically integrates the predefined rules located in the .cursor/rules directory. No additional setup is required—the rules will load automatically.

Cursor allows you to add specialized rules tailored for very specific tasks. These rules aren't loaded by default into the AI context but can easily be activated by mentioning them explicitly in the chat, enabling precise and focused interactions.

Visit [Cursor specialized tasks](cursor-specialized-prompts.md) to explore the specialized tasks supported by system-tests. Feel free to create and contribute as many specialized rules as you need—your teammates will greatly appreciate your efforts!

If you introduce new instructions, enhance existing documentation, or improve the predefined rules, you're strongly encouraged to add corresponding tests. These tests play a vital role in validating your enhancements and ensuring the AI assistant performs optimally. For further guidance, see section [Prompt validation](ai-tools-prompt-validation.md).

