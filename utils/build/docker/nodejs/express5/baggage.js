'use strict'

const http = require('http')

module.exports = (app) => {
  app.get('/otel_drop_in_baggage_api_datadog', (req, res) => {
    const {
      setBaggageItem,
      removeBaggageItem
    } = require('dd-trace/packages/dd-trace/src/baggage')

    const url = req.query.url
    const parsedUrl = new URL(url)
    const options = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || 80,
      path: parsedUrl.pathname,
      method: 'GET'
    }

    const baggageRemove = req.query.baggage_remove
    const baggageSet = req.query.baggage_set
    const baggageToRemove = baggageRemove ? baggageRemove.split(',') : []
    const baggageToSet = baggageSet
      ? baggageSet.split(',').map(item => item.split('='))
      : []

    for (const key of baggageToRemove) {
      removeBaggageItem(key.trim())
    }
    for (const [key, value] of baggageToSet) {
      setBaggageItem(key.trim(), value.trim())
    }

    const httpRequest = http.request(options, (response) => {
      let responseBody = ''
      response.on('data', (chunk) => {
        responseBody += chunk
      })
      response.on('end', () => {
        res.json({
          url,
          status_code: response.statusCode,
          request_headers: response.req._headers,
          response_headers: response.headers,
          response_body: responseBody
        })
      })
    })

    httpRequest.on('error', (error) => {
      console.log(error)
      res.json({
        url,
        status_code: 500,
        request_headers: null,
        response_headers: null
      })
    })

    httpRequest.end()
  })
}
