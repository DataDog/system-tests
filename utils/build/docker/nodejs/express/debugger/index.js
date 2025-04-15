'use strict'
/* eslint-disable no-unused-vars, camelcase */

const Pii = require('./pii')

module.exports = {
  initRoutes (app) {
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

    app.get('/debugger/log', (req, res) => {
      res.send('Log probe') // This needs to be line 20
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

    app.get('/debugger/pii', (req, res) => {
      const pii = new Pii()
      res.send('Hello World') // This needs to be line 64
    })

    app.get('/debugger/expression', (req, res) => {
      const { inputValue } = req.query
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
      res.send('Expression probe') // This needs to be line 82
    })

    app.get('/debugger/expression/operators', (req, res) => {
      const intValue = Number(req.query.intValue)
      const floatValue = Number(req.query.floatValue)
      const strValue = req.query.strValue
      const pii = new Pii()
      res.send('Expression probe') // This needs to be line 90
    })

    app.get('/debugger/expression/strings', (req, res) => {
      const { strValue } = req.query
      const emptyString = ''
      res.send('Expression probe') // This needs to be line 96
    })

    app.get('/debugger/expression/collections', (req, res) => {
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

      res.send('Expression probe') // This needs to be line 120
    })

    app.get('/debugger/expression/null', (req, res) => {
      const { intValue, strValue, boolValue } = req.query
      const pii = boolValue ? new Pii() : null
      res.send('Expression probe') // This needs to be line 126
    })
  }
}
