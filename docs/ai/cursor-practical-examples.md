# Cursor AI Practical Examples for System-Tests

## 🎯 Overview

This guide provides real-world, practical examples of using Cursor AI effectively with the system-tests repository.

## 🚀 Quick Start Examples

### Example 1: Basic System-Tests Questions
```markdown
# User Query:
# ✅ Good: General questions (auto-handled by always-applied rules)
"How do I run AWS SSI tests?"
"What are the requirements for system-tests?"
"How do I create a new end-to-end weblog?"
```

### Example 2: First-Time Setup
```markdown
# User Query:
"I'm new to system-tests. How do I get started?"
```

### Example 3: Understanding Scenarios
```markdown
# User Query:
"What scenarios are available in system-tests?"
```

## 🏗️ AWS SSI Development Examples

### Example 4: Virtual Machine Registration
```markdown
# User Query:
"I need to register a new Ubuntu 24 virtual machine for AWS SSI tests"
```

### Example 5: AWS SSI Weblog Creation
```markdown
# User Query:
"Create a new Node.js weblog provision for AWS SSI tests"
```

### Example 6: AWS SSI Scenario Creation
```markdown
# User Query:
"I want to create a new AWS SSI scenario for testing crash tracking"
```

## 🌐 End-to-End Development Examples

### Example 7: New End-to-End Weblog Creation
```markdown
# User Query:
"Create a new Python Flask weblog for end-to-end testing with database integration"
```

## ☸️ Kubernetes Examples

### Example 8: K8s Library Injection Setup
```markdown
# User Query:
"How do I run K8s library injection tests with private registry?"
```

## 🎯 Specialized Task Examples

### Example 9: Basic Specialized Java Development
```markdown
# User Query:
@.agents/rules/java-endpoint-prompt.md

Analyze this test file and create the missing endpoints for Spring Boot:

Framework: spring-boot
Test file: tests/appsec/iast/test_sqli.py
```
### Example 10: Multi-Framework Java Development
```markdown
# User Query:
@.agents/rules/java-endpoint-prompt.md

Create the same SQLI endpoint for Vert.x 4 and Jersey
```

## 🧪 Test activation

### Example 11: Test Activation/Deactivation
```markdown
# User Query:
"I need to disable the test XYZ for Python versions below 3.8"
```

## 🔧 Troubleshooting Examples

### Example 12: Test Activation/Deactivation throubleshooting
```markdown
# User Query:
"Why my test Test_Mongo is not being executed for my python tracer 1.8.9?"
```

### Example 13: AWS SSI Debugging
```markdown
# User Query:
"My AWS SSI test is failing. why?"
```

### Example 14: Build Issues
```markdown
# User Query:
"My Java weblog won't compile after adding new endpoints"
```

## 💡 Pro Tips and Best Practices

### Effective Communication Patterns
```markdown
# ✅ Good: Specific, contextual requests
"Create Spring Boot endpoints for IAST SQL injection testing based on test_sqli.py"

# ❌ Avoid: Vague requests
"Help me with Java"

# ✅ Good: Include scenario type context
"I'm working on AWS SSI tests and need to register a new VM"

# ❌ Avoid: Missing context
"How do I register something?"
```