'use strict'

const { ApolloServer, gql } = require('apollo-server-express')
const { readFileSync } = require('fs')

const users = [
  {
    id: 1,
    name: 'foo'
  },
  {
    id: 2,
    name: 'bar'
  },
  {
    id: 3,
    name: 'bar'
  }
]

const typeDefs = gql`
      directive @case(format: String) on FIELD

      type Query {
        user(id: Int!): User
        userByName(name: String): [User]
        testInjection(path: String): [User]
        withError: ID
      }

      type User {
        id: Int
        name: String
      }

      type Error {
        message: String
        extensions: [Extension]
      }

      type Extension {
        key: String
        value: String
      }`

function getUser (parent, args) {
  return users.find((item) => args.id === item.id)
}

function getUserByName (parent, args) {
  return users.filter((item) => args.name === item.name)
}

function testInjection (parent, args) {
  try {
    readFileSync(args.path)
  } catch {
    // do nothing
  }
  return users
}

function withError (parent, args) {
  throw new Error('test error')
}

const resolvers = {
  Query: {
    user: getUser,
    userByName: getUserByName,
    testInjection,
    withError
  }
}

// Custom error formatting
const formatError = (error) => {
  return {
    message: error.message,
    extensions: [
      { key: 'int', value: 1},
      { key: 'float', value: 1.1},
      { key: 'str', value: '1'},
      { key: 'bool', value: true},
      { key: 'other', value: [1, 'foo']},
      { key: 'not_captured', value: 'nope'},
    ]
  }
}

module.exports = async function (app) {
  const server = new ApolloServer({ typeDefs, resolvers, formatError })
  await server.start()
  server.applyMiddleware({ app })
}
