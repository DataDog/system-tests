'use strict'

import type { Express } from 'express'
const { ApolloServer, gql } = require('apollo-server-express')
const { readFileSync } = require('fs')

const users = [
  {
    id: 1,
    name: 'foo',
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

function getUser (parent: any, args: any) {
 return users.find((item) => args.id === item.id)
}

function getUserByName (parent: any, args: any) {
  return users.filter((item) => args.name === item.name)
}

function testInjection (parent: any, args: any) {
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

module.exports = async function (app: Express) {
  const server = new ApolloServer({ typeDefs, resolvers })
  await server.start()
  server.applyMiddleware({ app })
}
