package main

import (
	"context"
	"net/http"
	"weblog/internal/common"

	graphqltrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/graph-gophers/graphql-go"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"

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

func main() {
	tracer.Start()
	defer tracer.Stop()

	schema := graphql.MustParseSchema(schema, &query{}, graphql.Tracer(graphqltrace.NewTracer()))
	handler := &relay.Handler{Schema: schema}

	mux := http.NewServeMux()
	mux.HandleFunc("/graphql", func(w http.ResponseWriter, r *http.Request) {
		// Store the user-agent in context so we can add it to spans later on...
		r = r.WithContext(context.WithValue(r.Context(), userAgent{}, r.UserAgent()))
		handler.ServeHTTP(w, r)
	})

	// The / endpoint is used as a weblog heartbeat
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		// "/" is the default route when the others don't match
		// cf. documentation at https://pkg.go.dev/net/http#ServeMux
		// Therefore, we need to check the URL path to only handle the `/` case
		if r.URL.Path != "/" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		w.WriteHeader(http.StatusOK)
	})

	common.InitDatadog()

	http.ListenAndServe(":7777", mux)
}

type userAgent struct{}

type query struct{}

func (query) User(ctx context.Context, args struct{ ID int32 }) *user {
	if span, found := tracer.SpanFromContext(ctx); found {
		// Hack: the System-Tests rely on user-agent to filter spans for a given request... so we slap it on the span here.
		span.SetTag("http.request.headers.user-agent", ctx.Value(userAgent{}))
	}

	if name, found := users[args.ID]; found {
		return &user{id: args.ID, name: name}
	}
	return nil
}

func (query) UserByName(ctx context.Context, args struct{ Name *string }) []*user {
	if span, found := tracer.SpanFromContext(ctx); found {
		// Hack: the System-Tests rely on user-agent to filter spans for a given request... so we slap it on the span here.
		span.SetTag("http.request.headers.user-agent", ctx.Value(userAgent{}))
	}

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
