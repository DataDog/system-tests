package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"systemtests.weblog/_shared/common"

	graphqltrace "github.com/DataDog/dd-trace-go/contrib/graphql-go/graphql/v2"
	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
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
				"withError": &graphql.Field{
					Args:    graphql.FieldConfigArgument{},
					Type:    graphql.ID,
					Resolve: resolveWithError,
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

	mux.HandleFunc("/healthcheck", func(w http.ResponseWriter, r *http.Request) {

		healthCheck, err := common.GetHealtchCheck()
		if err != nil {
			http.Error(w, "Can't get JSON data", http.StatusInternalServerError)
		}

		jsonData, err := json.Marshal(healthCheck)
		if err != nil {
			http.Error(w, "Can't build JSON data", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write(jsonData)
	})

	srv := &http.Server{
		Addr:    ":7777",
		Handler: mux,
	}
	common.InitDatadog()
	go func() {
		if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			log.Fatal(err)
		}
	}()

	c := make(chan os.Signal, 1)
	signal.Notify(c, syscall.SIGTERM)
	<-c

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("HTTP shutdown error: %v", err)
	}
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

func resolveWithError(_ graphql.ResolveParams) (any, error) {
	return nil, customError{
		message: "test error",
		extensions: map[string]any{
			"int":          1,
			"float":        1.1,
			"str":          "1",
			"bool":         true,
			"other":        []any{1, "foo"},
			"not_captured": "nope",
		},
	}
}

type customError struct {
	message    string
	extensions map[string]any
}

func (e customError) Error() string {
	return e.message
}

func (e customError) Extensions() map[string]any {
	return e.extensions
}
