function initRoutes (fastify) {
  console.log('Api Gateway routes initialized.')

  fastify.get('/inferred-proxy/span-creation', async (request, reply) => {
    const statusCode = parseInt(request.query.status_code, 10)

    console.log('Received an API Gateway request')
    console.log('Request headers:', request.headers)

    reply.status(statusCode)
    return 'ok'
  })
}

module.exports = { initRoutes }
