# Java Weblog Development with Cursor IDE

This directory contains tools and configurations for Java weblog development in **system-tests** using **Cursor IDE**.

## 📋 Table of Contents

- [Description](#description)
- [Core Workflow](#core-workflow)
- [Prerequisites](#prerequisites)
- [Manual Setup](#manual-setup)
- [Using the Prompt](#using-the-prompt)
- [Supported Frameworks](#supported-frameworks)
- [Development Workflow](#development-workflow)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🎯 Description

The `java-endpoint-prompt.mdc` file is a **specialized prompt** for Cursor IDE that contains:

- **Implementation guidelines** for Java endpoints in system-tests weblogs
- **Framework-specific patterns** for each framework (Spring Boot, Vert.x, Jersey, etc.)
- **Critical rules** for preserving existing code
- **Best practices** for development and testing

## 🚀 Core Workflow

The **fundamental way to work** with this prompt is to **create endpoints from test files**. Here's how it works:

### 📝 Test-Driven Endpoint Creation

1. **Start with a test file** (e.g., `tests/appsec/iast/test_sqli.py`)
2. **Feed the test to Cursor** with the prompt
3. **Cursor analyzes the test** and extracts the required endpoints
4. **Cursor generates the implementation** following the framework patterns

### 💡 Example Usage

```markdown
@java-endpoint-prompt.mdc

Analyze this test file and create the missing endpoints for Spring Boot:

[paste test file content or reference the test file]

Framework: spring-boot
Test file: tests/appsec/iast/test_sqli.py
```

**Cursor will:**
- 🔍 **Extract endpoint requirements** from the test (paths, methods, parameters)
- 🏗️ **Generate the Java implementation** using the correct framework patterns
- ⚡ **Follow preservation rules** to avoid breaking existing code
- 🎯 **Create only what's needed** based on the test specifications

## 💡 Using the Prompt

### Useful Cursor Commands

Once you have the prompt loaded, you can use commands like:

```markdown
# Create endpoints from test file (RECOMMENDED APPROACH)
@java-endpoint-prompt.mdc Analyze this test file and create the missing endpoints for Spring Boot:
[paste test content or reference test file]

# Create a specific endpoint
@java-endpoint-prompt.mdc Create a POST /iast/sqli/test endpoint for Spring Boot

# Analyze existing endpoint
@java-endpoint-prompt.mdc Analyze the /rasp/lfi endpoint in vertx4

# Fix build issues
@java-endpoint-prompt.mdc Help me fix this compilation error in Jersey
```

### Request Structure

For best results, structure your requests like this:

```markdown
@java-endpoint-prompt.mdc

Framework: [spring-boot/vertx3/vertx4/jersey-grizzly2/etc.]
Test file: [path/to/test_file.py] (RECOMMENDED)
Action: [analyze-test/create/modify/debug]

Detailed description of what you need...
```

### 🎯 Test-First Approach (Recommended)

The most effective way to use this prompt:

```markdown
@java-endpoint-prompt.mdc

Framework: spring-boot
Test file: tests/appsec/iast/test_sql_injection.py

Please analyze this test file and create all the missing endpoints that are needed for the test to pass.
```

## 🛠️ Supported Frameworks

The prompt includes specific configurations for:

| Framework | Directory | Characteristics |
|-----------|-----------|-----------------|
| **Spring Boot** | `spring-boot/` | Annotations, Controllers, RequestMapping |
| **Vert.x 3** | `vertx3/` | Route Providers, Consumer<Router> |
| **Vert.x 4** | `vertx4/` | Route Providers, Consumer<Router> |
| **Jersey** | `jersey-grizzly2/` | JAX-RS, Resource Classes |
| **Play** | `play/` | Scala Controllers, Actions |
| **Ratpack** | `ratpack/` | Handler Classes, Chain |
| **Akka-HTTP** | `akka-http/` | Scala DSL, Route Objects |
| **RESTEasy** | `resteasy-netty3/` | JAX-RS, Resource Classes |

## 🔄 Development Workflow

### 1. Test-Driven Endpoint Development

```bash
# 1. Analyze test file to understand requirements
@java-endpoint-prompt.mdc Analyze this test file and extract endpoint requirements:
[paste or reference test file]

# 2. Find existing implementations in other languages (optional)
@java-endpoint-prompt.mdc Search for similar endpoints in other languages

# 3. Generate endpoints based on test analysis
@java-endpoint-prompt.mdc Create the missing endpoints for [framework] based on the test analysis

# 4. Build and validate
./utils/build/build.sh --library java --weblog-variant spring-boot

# 5. Run the test
./run.sh tests/path/to/test_file.py
```

### 2. Debugging

```bash
# For compilation errors
@java-endpoint-prompt.mdc Analyze this build error: [error]

# For test failures
@java-endpoint-prompt.mdc This test fails with 404, what should I check?
```

## 🚨 Troubleshooting

### Cursor doesn't see the file

**Problem**: Cursor doesn't recognize the prompt
**Solution**:
1. Verify you're in the correct directory
2. Use the full path: `@utils/build/docker/java/.cursor/rules/java-endpoint-prompt.mdc`
3. Restart Cursor IDE

### Generic responses

**Problem**: Cursor gives generic responses without following the rules
**Solution**:
1. Make sure to reference the file with `@java-endpoint-prompt.mdc`
2. Specify the framework in your request
3. Include specific endpoint context
4. **Use the test-first approach** for better results

### Build errors

**Problem**: Generated code doesn't compile
**Solution**:
1. Verify that existing imports haven't been removed
2. Check that class fields are preserved
3. Consult the troubleshooting section in the prompt

### Test analysis issues

**Problem**: Cursor doesn't extract endpoints correctly from tests
**Solution**:
1. Make sure to reference both the prompt and the test file clearly
2. Specify the target framework
3. Provide the complete test file content or path
4. Ask for step-by-step analysis if needed

## 🤝 Contributing

### Improving the Prompt

If you find patterns or rules that should be added:

1. **Edit** `java-endpoint-prompt.mdc`
2. **Test** the changes with various frameworks
3. **Document** the changes in this README

## 📚 Additional Resources

- [Weblog Documentation](../../../docs/weblog/)
- [System-Tests Scenarios](../../../docs/scenarios/)
- [Development Guide](../../../docs/edit/)
- [Slack: #apm-shared-testing](https://datadoghq.slack.com/channels/apm-shared-testing)

---

**📋 DOCUMENTATION USED**: @java-endpoint-prompt.mdc, @docs/weblog/, @docs/scenarios/