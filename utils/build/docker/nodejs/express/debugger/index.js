'use strict'
/* eslint-disable no-unused-vars, camelcase */

const { Pii, createPiiLocals } = require('./pii')
const dataGenerator = require('./data_generator')

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
      const { pii, password, user, customPii } = createPiiLocals()
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

    app.get('/debugger/snapshot/limits', (req, res) => {
      const { deepObject, manyFields, largeCollection, longString } = dataGenerator({
        depth: parseInt(req.query.depth, 10) || 0,
        fields: parseInt(req.query.fields, 10) || 0,
        collectionSize: parseInt(req.query.collectionSize, 10) || 0,
        stringLength: parseInt(req.query.stringLength, 10) || 0
      })
      res.send('Capture limits probe') // This needs to be line 136
    })

    app.get('/debugger/snapshot/capture-timeout', (req, res) => {
      const collectionSize = parseInt(req.query.collectionSize, 10) || 0
      const nestingDepth = parseInt(req.query.nestingDepth, 10) || 0
      res.send(captureTimeoutFixture(collectionSize, nestingDepth))
    })

    app.get('/debugger/budgets/:loops', budgets)
    app.get('/debugger/correlation', correlationHandler)
    app.get('/debugger/correlation/loop/:count', correlationLoopHandler)
  }
}

function captureTimeoutFixture (collectionSize, nestingDepth) {
  const largeCollection = Array.from({ length: collectionSize }, (_, index) => {
    let nested = { value: index }
    for (let level = nestingDepth; level > 0; level--) {
      nested = { level, nested }
    }
    return nested
  })
  return 'Capture timeout probe' // This needs to be line 159
}

function budgets (request, reply) {
  const loops = Number(request.params.loops)
  for (let iteration = 0; iteration < loops; iteration++) {
    const currentIteration = iteration // This needs to be line 165
  }
  return reply.send('Budgets')
}

async function correlationHandler (req, res) {
  res.send(`Correlation ${await correlation()}`)
}

async function correlation () {
  const value = await correlationMiddle()
  await sleep(400)
  return value // This needs to be line 177
}

async function correlationMiddle () {
  const value = correlationLeaf()
  await sleep(400)
  return value // This needs to be line 183
}

function correlationLeaf () {
  return 3 // This needs to be line 187
}

async function correlationLoopHandler (req, res) {
  const count = Number(req.params.count)
  let total = 0
  for (let i = 0; i < count; i++) {
    total += i // This needs to be line 194
    await sleep(1000)
  }
  res.send(`Loop ${total}`) // This needs to be line 197
}

function sleep (ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
