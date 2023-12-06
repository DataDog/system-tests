const express = require('express');
const app = express();
const port = 3000; // You can change this to any port you prefer



// Additional Endpoints
app.get('/trace/span/start', (req, res) => {
  // Logic for /trace/span/start endpoint
  res.send('Span started successfully!');
});

app.get('/trace/span/finish', (req, res) => {
  // Logic for /trace/span/finish endpoint
  res.send('Span finished successfully!');
});

app.get('/trace/span/set_meta', (req, res) => {
  // Logic for /trace/span/set_meta endpoint
  res.send('Meta set successfully!');
});

app.get('/trace/span/set_metric', (req, res) => {
  // Logic for /trace/span/set_metric endpoint
  res.send('Metric set successfully!');
});

app.get('/trace/stats/flush', (req, res) => {
  // Logic for /trace/stats/flush endpoint
  res.send('Stats flushed successfully!');
});

app.get('/trace/span/error', (req, res) => {
  // Logic for /trace/span/error endpoint
  res.send('Error reported successfully!');
});


// Endpoint /trace/span/inject_headers
app.get('/trace/span/inject_headers', (req, res) => {
    // Your logic to handle the endpoint goes here
    // For example, you can inject headers or perform any other action
    
    // Sending a response for demonstration purposes
    res.send('Headers injected successfully!');
  });


app.get('/trace/otel/start_span', (req, res) => {
  // Logic for /trace/otel/start_span endpoint
  res.send('OTEL span started successfully!');
});

app.get('/trace/otel/end_span', (req, res) => {
  // Logic for /trace/otel/end_span endpoint
  res.send('OTEL span ended successfully!');
});

app.get('/trace/otel/flush', (req, res) => {
  // Logic for /trace/otel/flush endpoint
  res.send('OTEL flushed successfully!');
});

app.get('/trace/otel/is_recording', (req, res) => {
  // Logic for /trace/otel/is_recording endpoint
  res.send('OTEL recording status checked successfully!');
});

app.get('/trace/otel/span_context', (req, res) => {
  // Logic for /trace/otel/span_context endpoint
  res.send('OTEL span context retrieved successfully!');
});

app.get('/trace/otel/set_status', (req, res) => {
  // Logic for /trace/otel/set_status endpoint
  res.send('OTEL status set successfully!');
});

app.get('/trace/otel/set_name', (req, res) => {
  // Logic for /trace/otel/set_name endpoint
  res.send('OTEL span name set successfully!');
});

app.get('/trace/otel/set_attributes', (req, res) => {
  // Logic for /trace/otel/set_attributes endpoint
  res.send('OTEL attributes set successfully!');
});

app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
