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
      }

      type User {
        id: Int
        name: String
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

const resolvers = {
  Query: {
    user: getUser,
    userByName: getUserByName,
    testInjection
  }
}

module.exports = async function (app) {
  const server = new ApolloServer({ typeDefs, resolvers })
  await server.start()
  server.applyMiddleware({ app })
}
