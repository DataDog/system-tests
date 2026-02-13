const tracer = require('dd-trace').init({});

const express = require('express');

const app = express();
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

const { GoogleGenAI } = require('@google/genai');
const genai = new GoogleGenAI({
  httpOptions: {
    baseUrl: `${process.env.DD_TRACE_AGENT_URL}/vcr/genai`
  }
});


app.get('/', (req, res) => {
  res.set('Content-Type', 'text/plain');
  res.send('Hello world!\n');
});

app.post('/generate_content', async (req, res) => {
  const { model, contents, config = {} } = req.body;

    const stream = config.stream;
    delete config.stream;

    const options = {
      model,
      contents: normalizeGoogleGenAiContents(contents),
      config: normalizeConfig(config)
    }

    let response;

    if (stream) {
      response = [];
      const stream = await genai.models.generateContentStream(options);
      for await (const chunk of stream) {
        response.push(chunk);
      }
    } else {
      response = await genai.models.generateContent(options);
    }

    res.json({ response });
});

app.post('/embed_content', async (req, res) => {
  const { model, contents, config = {} } = req.body;
  const response = await genai.models.embedContent({ model, contents, config: normalizeConfig(config) });
  res.json({ response });
});

function normalizeSnakeCaseConfigToCamelCase (obj) {
  const normalizedConfig = {};
  for (const key of Object.keys(obj)) {
    // turn keys into camelCase
    const camelKey = key.replace(/_([a-z])/g, (_, p1) => p1.toUpperCase());
    normalizedConfig[camelKey] = obj[key];
    if (key !== camelKey) {
      delete normalizedConfig[key];
    }
  }

  return normalizedConfig;
}

function normalizeGoogleGenAiContents (contents) {
  if (typeof contents === 'string') {
    return contents;
  }

  if (!Array.isArray(contents)) {
    contents = [contents];
  }

  return contents.map(content => {
    if (typeof content === 'string') return content;

    const normalizeContent = content;

    if (content.parts) {
      normalizeContent.parts = content.parts.map(part => {
        if (typeof part === 'string') return part;

        return normalizeSnakeCaseConfigToCamelCase(part);
      })

      return normalizeContent;
    } else {
      return normalizeSnakeCaseConfigToCamelCase(content);
    }
  })
}

function normalizeConfig (config) {
  const normalizedConfig = normalizeSnakeCaseConfigToCamelCase(config);

  // special-case thinking config
  if (normalizedConfig.thinkingConfig) {
    normalizedConfig.thinkingConfig = normalizeSnakeCaseConfigToCamelCase(normalizedConfig.thinkingConfig);
  }

  // special-case tools configs
  if (Array.isArray(normalizedConfig.tools)) {
    normalizedConfig.tools = normalizedConfig.tools.map(tool => {
      const normalizedTool = {};

      if (tool.function_declarations) {
        normalizedTool.functionDeclarations = tool.function_declarations;
      }

      if (tool.code_execution) {
        normalizedTool.codeExecution = tool.code_execution;
      }

      return normalizedTool;
    })
  }

  return normalizedConfig;
}

const port = process.env.FRAMEWORK_TEST_CLIENT_SERVER_PORT || 80
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
