const express = require('express');

const app = express();
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

const OpenAI = require('openai');
const client = new OpenAI({
  baseURL: `${process.env.DD_TRACE_AGENT_URL}/vcr/openai`
});

app.post('/chat/completions', async (req, res) => {
  const { model, messages, parameters } = req.body;
  const stream = parameters.stream;

  if (stream) {
    parameters.stream_options = {
      include_usage: true
    };
  }

  let response = await client.chat.completions.create({
    model,
    messages,
    ...parameters
  });

  if (stream) {
    const chunks = [];
    for await (const chunk of response) {
      chunks.push(chunk);
    }
    response = chunks;
  }

  res.json({ response });
});

app.post('/completions', async (req, res) => {
  const { model, prompt, parameters } = req.body;
  const response = await client.completions.create({
    model,
    prompt,
    ...parameters,
  });

  res.json({ response });
});

app.post('/embeddings', async (req, res) => {
  const { model, input } = req.body;
  const response = await client.embeddings.create({
    model,
    input,
  });

  res.json({ response });
});

app.post('/responses/create', async (req, res) => {
  const { model, input, parameters } = req.body;
  const response = await client.responses.create({
    model,
    input,
    ...parameters,
  });
  res.json({ response });
});

app.listen(process.env.FRAMEWORK_TEST_CLIENT_SERVER_PORT || 80, () => {
  console.log('Server is running on port 3000');
});
