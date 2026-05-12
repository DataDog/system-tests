const tracer = require('dd-trace').init({});

const express = require('express');

const app = express();
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

const { Anthropic } = require('@anthropic-ai/sdk');
const anthropic = new Anthropic({
  baseURL: `${process.env.DD_TRACE_AGENT_URL}/vcr/anthropic`
});

app.post('/create', async (req, res) => {
  const { model, messages, parameters, extra_headers } = req.body;

  const httpOptions = extra_headers ? { headers: extra_headers } : null;

  let response = await anthropic.messages.create({
    model,
    messages,
    ...parameters,
  }, httpOptions);

  if (parameters.stream) {
    const chunks = [];
    for await (const chunk of response) {
      chunks.push(chunk);
    }
    response = chunks;
  }

  res.json({ response });
});

app.post('/stream', async (req, res) => {
  const { model, messages, parameters } = req.body;

  let response = await anthropic.messages.stream({
    model,
    messages,
    ...parameters,
  });

  const chunks = [];
  for await (const chunk of response) {
    chunks.push(chunk);
  }
  response = chunks;

  res.json({ response });
});

app.listen(process.env.FRAMEWORK_TEST_CLIENT_SERVER_PORT || 80, () => {
  console.log('Server is running on port 3000');
});
