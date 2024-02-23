package main

import (
	"net/http"
	"weblog/internal/common"

	graphqltrace "github.com/DataDog/dd-trace-go/v2/contrib/graphql-go/graphql"
	httptrace "github.com/DataDog/dd-trace-go/v2/contrib/net/http"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"

	"github.com/graphql-go/graphql"
	"github.com/graphql-go/handler"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	userType := graphql.NewObject(graphql.ObjectConfig{
		Name: "User",
		Fields: graphql.Fields{
			"id":   &graphql.Field{Type: graphql.NewNonNull(graphql.Int)},
			"name": &graphql.Field{Type: graphql.NewNonNull(graphql.String)},
		},
	})
	schema, err := graphqltrace.NewSchema(graphql.SchemaConfig{
		Directives: []*graphql.Directive{
			graphql.NewDirective(graphql.DirectiveConfig{
				Name:      "case",
				Args:      graphql.FieldConfigArgument{"format": &graphql.ArgumentConfig{Type: graphql.String}},
				Locations: []string{graphql.DirectiveLocationField},
			}),
		},
		Query: graphql.NewObject(graphql.ObjectConfig{
			Name: "Query",
			Fields: graphql.Fields{
				"user": &graphql.Field{
					Args: graphql.FieldConfigArgument{
						"id": &graphql.ArgumentConfig{Type: graphql.NewNonNull(graphql.Int)},
					},
					Type:    userType,
					Resolve: resolveUser,
				},
				"userByName": &graphql.Field{
					Args: graphql.FieldConfigArgument{
						"name": &graphql.ArgumentConfig{Type: graphql.String},
					},
					Type:    graphql.NewNonNull(graphql.NewList(graphql.NewNonNull(userType))),
					Resolve: resolveUserByName,
				},
			},
		}),
	})
	if err != nil {
		panic(err)
	}

	handler := handler.New(&handler.Config{Schema: &schema, Pretty: true, GraphiQL: true})

	mux := httptrace.NewServeMux()
	mux.Handle("/graphql", handler)

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

	panic(http.ListenAndServe(":7777", mux))
}

type user struct {
	ID   int
	Name string
}

var users = map[int]string{
	1: "foo",
	2: "bar",
	3: "bar",
}

func resolveUser(p graphql.ResolveParams) (any, error) {
	id := p.Args["id"].(int)
	if name, found := users[id]; found {
		return &user{ID: id, Name: name}, nil
	}
	return nil, nil
}

func resolveUserByName(p graphql.ResolveParams) (any, error) {
	name := p.Args["name"]
	if name == nil {
		name = ""
	}

	strName := name.(string)
	result := make([]*user, 0, len(users))

	for id, name := range users {
		if name == strName {
			result = append(result, &user{ID: id, Name: name})
		}
	}

	return result, nil
}
