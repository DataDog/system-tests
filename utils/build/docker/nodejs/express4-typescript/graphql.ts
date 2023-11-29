'use strict'

import type { Express } from 'express'
const { ApolloServer, gql } = require('apollo-server-express')

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
      type Query {
        user(id: Int!): User
        userByName(name: String): [User]
      }

      type User {
        id: Int
        name: String
      }`

function getUser (args: any) {
 return users.find((item) => args.id === item.id)
}

function getUserByName (args: any) {
  return users.filter((item) => args.name === item.name)
}

const resolvers = {
  Query: {
    user: getUser,
    userByName: getUserByName
  }
}

module.exports = async function (app: Express) {
  const server = new ApolloServer({ typeDefs, resolvers })
  await server.start()
  server.applyMiddleware({ app })
}
