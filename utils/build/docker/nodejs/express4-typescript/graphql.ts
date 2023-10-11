'use strict'

import type { Express } from 'express'
const  { graphqlHTTP } = require('express-graphql')
const { buildSchema } = require('graphql')

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

const schema = buildSchema(`
      type Query {
        user(id: Int!): User
        userByName(name: String): [User]
      }

      type User {
        id: Int
        name: String
      }
`);

function getuser (args: any) {
 return users.find((item) => args.id === item.id)
}

function getUserByName (args: any) {
  return users.filter((item) => args.name === item.name)
}

const rootValue = {
  user: getuser,
  userByName: getUserByName
}

module.exports = function (app: Express) {
  app.use(
    '/graphql',
    graphqlHTTP({
      schema,
      rootValue,
      graphiql: true
    })
  )
}
