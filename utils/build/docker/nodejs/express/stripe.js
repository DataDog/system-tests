'use strict'

const stripe = require('stripe')('sk_test_FAKE', {
  host: 'stripe-mock',
  port: 12111,
  protocol: 'http',
  telemetry: false
})

function init (app) {
  app.post('/stripe/create_checkout_session', async (req, res) => {
    console.log('received request')
    const result = await stripe.checkout.sessions.create({
      client_reference_id: 'superdiaz',
      line_items: [
        {
          price_data: {
            currency: 'eur',
            product_data: {
              name: 'test'
            },
            unit_amount: 100
          },
          quantity: 100
        }
      ],
      mode: 'payment',
      customer_email: 'topkek@topkek.com',
      discounts: [{
        //coupon: 'J7BN15vk',
        promotion_code: 'promo_1SEBV4A8AZcqnBxYVOzXjPVu'
      }],
      shipping_options: [{
        shipping_rate_data: {
          display_name: 'test',
          fixed_amount: {
            amount: 100,
            currency: 'eur'
          },
          type: 'fixed_amount'
        }
      }]
    })

    console.log('strpie relut', result)

    res.json(result)
  })

  app.post('/webhook')
}

module.exports = init
