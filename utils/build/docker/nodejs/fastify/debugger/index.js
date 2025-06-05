'use strict'
/* eslint-disable no-unused-vars, camelcase */

const Pii = require('./pii')

module.exports = {
  initRoutes (fastify) {
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding

    fastify.get('/debugger/log', async (request, reply) => {
      return 'Log probe' // This needs to be line 20
    })

    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding
    // Padding

    fastify.get('/debugger/pii', async (request, reply) => {
      const pii = new Pii()
      return 'Hello World' // This needs to be line 64
    })

    fastify.get('/debugger/expression', async (request, reply) => {
      const { inputValue } = request.query
      const localValue = 3
      const testStruct = {
        IntValue: 1,
        DoubleValue: 1.1,
        StringValue: 'one',
        BoolValue: true,
        Collection: ['one', 'two', 'three'],
        Dictionary: {
          one: 1,
          two: 2,
          three: 3
        }
      }
      return 'Expression probe' // This needs to be line 82
    })

    fastify.get('/debugger/expression/operators', async (request, reply) => {
      const intValue = Number(request.query.intValue)
      const floatValue = Number(request.query.floatValue)
      const strValue = request.query.strValue
      const pii = new Pii()
      return 'Expression probe' // This needs to be line 90
    })

    fastify.get('/debugger/expression/strings', async (request, reply) => {
      const { strValue } = request.query
      const emptyString = ''
      return 'Expression probe' // This needs to be line 96
    })

    fastify.get('/debugger/expression/collections', async (request, reply) => {
      const a0 = []
      const l0 = []
      const h0 = {}
      const a1 = [1]
      const l1 = [1]
      const h1 = { 0: 0 }
      const a5 = [0, 1, 2, 3, 4]
      const l5 = [0, 1, 2, 3, 4]
      const h5 = { 0: 0, 1: 1, 2: 2, 3: 3, 4: 4 }

      const a0_count = a0.length
      const l0_count = l0.length
      const h0_count = Object.keys(h0).length
      const a1_count = a1.length
      const l1_count = l1.length
      const h1_count = Object.keys(h1).length
      const a5_count = a5.length
      const l5_count = l5.length
      const h5_count = Object.keys(h5).length

      return 'Expression probe' // This needs to be line 120
    })

    fastify.get('/debugger/expression/null', async (request, reply) => {
      const { intValue, strValue, boolValue } = request.query
      const pii = boolValue ? new Pii() : null
      return 'Expression probe' // This needs to be line 126
    })
  }
}
