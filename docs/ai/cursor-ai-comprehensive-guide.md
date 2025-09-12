# Cursor AI and System-Tests: Comprehensive Integration Guide

## 🎯 Overview

This guide provides comprehensive documentation about the AI integration capabilities in the `system-tests` repository, with a focus on **Cursor AI** and the `.cursor` rules structure. The AI tools are designed to enhance developer productivity when implementing tests, troubleshooting issues, and working with complex testing scenarios.

## 📁 The .cursor Folder Structure

The `.cursor` folder contains the AI configuration and rules that make the system-tests repository AI-ready. Here's the complete structure:

```
.cursor/
└── rules/                           # AI rules directory
    ├── aws-ssi-testing.mdc         # AWS SSI (Single Step Instrumentation) testing rules
    ├── code-format-standards.mdc    # Code formatting and quality standards
    ├── end-to-end-testing.mdc      # End-to-end testing scenarios rules
    ├── fine-tuning-guidance.mdc    # General fine-tuning and guidance rules
    ├── general-behavior.mdc        # General AI behavior and communication rules
    ├── java-endpoint-prompt.mdc    # Specialized Java endpoint development rules
    ├── k8s-ssi.mdc                 # Kubernetes SSI testing rules
    ├── promptfoo-llm.mdc           # LLM testing and validation rules
    ├── repository-structure.mdc    # Repository structure and navigation rules
    ├── system-tests-overview.mdc   # High-level system-tests overview rules
    └── test-activation.mdc         # Test activation and deactivation rules
```

### 📋 Rules File Categories

#### 🔧 **Core Functionality Rules** (Always Applied)
- **`general-behavior.mdc`**: Defines communication style, documentation referencing, and basic AI behavior
- **`fine-tuning-guidance.mdc`**: Core guidance for interpreting documentation, file references, and repository navigation
- **`system-tests-overview.mdc`**: Fundamental understanding of what system-tests is and main concepts
- **`repository-structure.mdc`**: Detailed repository structure with comments for each folder

#### 🏗️ **Testing Domain Rules** (Always Applied)
- **`aws-ssi-testing.mdc`**: Comprehensive rules for AWS Single Step Instrumentation testing
- **`end-to-end-testing.mdc`**: End-to-end testing scenarios, weblogs, and test implementation
- **`k8s-ssi.mdc`**: Kubernetes library injection testing rules
- **`test-activation.mdc`**: Rules for enabling/disabling tests using manifests and decorators
- **`code-format-standards.mdc`**: Code quality standards for shell, Python, and YAML

#### 🎯 **Specialized Task Rules** (Manual Activation)
- **`java-endpoint-prompt.mdc`**: Comprehensive Java weblog endpoint development specialist
- **`promptfoo-llm.mdc`**: LLM testing framework for validating AI prompts and responses

## 🚀 Getting Started with Cursor AI

### 1. Basic Setup
Cursor AI automatically loads all rules marked with `alwaysApply: true`. No additional setup is required for basic functionality.

### 2. Understanding Rule Types

#### Always Applied Rules
These rules are automatically loaded when you start Cursor:
```yaml
---
description:
globs:
alwaysApply: true
---
```

#### Manual Rules
These specialized rules require explicit activation:
```yaml
---
description: "Specialized Java endpoint development"
globs: ["**/*.java"]
alwaysApply: false
---
```

**📖 See: [Cursor AI Practical Examples](cursor-practical-examples.md)**

