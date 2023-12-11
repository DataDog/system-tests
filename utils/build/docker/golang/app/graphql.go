package main

import (
	"net/http"

	graphql "github.com/graph-gophers/graphql-go"
	"github.com/graph-gophers/graphql-go/relay"
)

const schema = `
directive @case(format: String) on FIELD

type Query {
	user(id: Int!): User
	userByName(name: String): [User!]!
}

type User {
	id: Int!
	name: String!
}
`

func NewGraphQLHandler() http.Handler {
	schema := graphql.MustParseSchema(schema, &query{})

	return &relay.Handler{Schema: schema}
}

type query struct{}

func (query) User(args struct{ ID int32 }) *user {
	if name, found := users[args.ID]; found {
		return &user{id: args.ID, name: name}
	}
	return nil
}

func (query) UserByName(args struct{ Name *string }) []*user {
	if args.Name == nil {
		args.Name = new(string)
	}

	result := make([]*user, 0, len(users))
	for id, name := range users {
		if name == *args.Name {
			result = append(result, &user{id: id, name: name})
		}
	}
	return result
}

type user struct {
	id   int32
	name string
}

func (u *user) ID() int32 {
	return u.id
}

func (u *user) Name() string {
	return u.name
}

var users = map[int32]string{
	1: "foo",
	2: "bar",
	3: "bar",
}
