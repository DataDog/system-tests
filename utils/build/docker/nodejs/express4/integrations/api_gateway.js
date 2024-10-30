function initRoutes (app, tracer) {
  console.log('Api Gateway routes initialized.')

  app.get('/api-gateway/span-creation', (req, res) => {
    const statusCode = parseInt(req.query.status_code, 10)

    console.log('Received an API Gateway request')
    console.log('Request headers:', req.headers)

    res.status(statusCode).send('ok')
  })
}

module.exports = { initRoutes }
