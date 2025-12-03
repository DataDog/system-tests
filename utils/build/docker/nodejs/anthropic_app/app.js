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
  const {
    model,
    messages,
    parameters,
    stream_as_method,
  } = req.body;

  const options = {
    model,
    messages,
    ...parameters,
  };

  let response = {};

  if (parameters.stream) {
    response = await anthropic.messages.stream(options);

    const chunks = [];
    for await (const chunk of response) {
      chunks.push(chunk);
    }
    response = chunks;
  } else if (parameters.stream) {
    delete options.stream;
    response = await anthropic.messages.create(options);

    const chunks = [];
    for await (const chunk of response) {
      chunks.push(chunk);
    }
    response = chunks;
  } else {
    response = await anthropic.messages.create(options);
  }

  res.json({ response });
});

app.listen(process.env.FRAMEWORK_TEST_CLIENT_SERVER_PORT || 80, () => {
  console.log('Server is running on port 3000');
});
