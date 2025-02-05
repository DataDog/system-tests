'use strict'

const { ApolloServer, gql, ApolloError } = require('apollo-server-express')
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
`

// Custom GraphQL error class
class CustomGraphQLError extends ApolloError {
  constructor (message, code, properties) {
    super(message, properties)
    this.extensions.code = code
    this.extensions.int = 1
    this.extensions.float = 1.1
    this.extensions.str = '1'
    this.extensions.bool = true
    this.extensions.other = [1, 'foo']
    this.extensions.not_captured = 'nope'
  }
}

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
  throw new CustomGraphQLError('test error', 'CUSTOM_USER_DEFINED_ERROR', 'Some extra context about the error.')
}

const resolvers = {
  Query: {
    user: getUser,
    userByName: getUserByName,
    testInjection,
    withError
  }
}

module.exports = async function (app) {
  const server = new ApolloServer({ typeDefs, resolvers })
  await server.start()
  server.applyMiddleware({ app })
}
