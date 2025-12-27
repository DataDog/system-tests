'use strict'

const stripe = require('stripe')('sk_FAKE', {
  host: 'internal_server',
  port: 8089,
  protocol: 'http',
  telemetry: false
})

const webhookSecret = 'whsec_FAKE'

function init (app) {
  app.post('/stripe/create_checkout_session', async (req, res) => {
    const result = await stripe.checkout.sessions.create(req.body)

    res.json(result)
  })

  app.post('/stripe/create_payment_intent', async (req, res) => {
    const result = await stripe.paymentIntents.create(req.body)

    res.json(result)
  })

  app.post('/stripe/webhook', async (req, res) => {
    const event = stripe.webhooks.constructEvent(
      req.rawBody,
      req.headers['stripe-signature'],
      webhookSecret
    )

    res.json(event)
  })
}

module.exports = init
