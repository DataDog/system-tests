package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/DataDog/dd-trace-go/v2/appsec"
	chitrace "github.com/DataDog/dd-trace-go/v2/contrib/go-chi/chi.v5"
	httptrace "github.com/DataDog/dd-trace-go/v2/contrib/net/http"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	mux := chi.NewRouter().With(chitrace.Middleware())

	mux.HandleFunc("/waf", func(w http.ResponseWriter, r *http.Request) {
		body, err := parseBody(r)
		if err == nil {
			appsec.MonitorParsedHTTPBody(r.Context(), body)
		}
		w.Write([]byte("Hello, WAF!\n"))
	})

	mux.HandleFunc("/waf/*", func(w http.ResponseWriter, r *http.Request) {
		body, err := parseBody(r)
		if err == nil {
			appsec.MonitorParsedHTTPBody(r.Context(), body)
		}
		w.Write([]byte("Hello, WAF!\n"))
	})

	mux.HandleFunc("/users", func(w http.ResponseWriter, r *http.Request) {
		userId := r.URL.Query().Get("user")
		if err := appsec.SetUser(r.Context(), userId); err != nil {
			return
		}
		w.Write([]byte("Hello, user!"))
	})

	mux.HandleFunc("/sample_rate_route/{i}", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/params/{myParam}", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/tag_value/{tag_value}/{status_code}", func(w http.ResponseWriter, r *http.Request) {
		ctx := chi.RouteContext(r.Context())
		tag := ctx.URLParam("tag_value")
		status, _ := strconv.Atoi(ctx.URLParam("status_code"))

		span, _ := tracer.SpanFromContext(r.Context())
		span.SetTag("appsec.events.system_tests_appsec_event.value", tag)
		w.WriteHeader(status)
		w.Write([]byte("Value tagged"))
	})

	mux.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		if c := r.URL.Query().Get("code"); c != "" {
			if code, err := strconv.Atoi(c); err == nil {
				w.WriteHeader(code)
			}
		}
		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/make_distant_call", func(w http.ResponseWriter, r *http.Request) {
		if url := r.URL.Query().Get("url"); url != "" {
			client := httptrace.WrapClient(http.DefaultClient)
			req, _ := http.NewRequestWithContext(r.Context(), http.MethodGet, url, nil)
			_, err := client.Do(req)

			if err != nil {
				log.Fatalln(err)
				w.WriteHeader(500)
			}
		}
		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/headers/", headers)
	mux.HandleFunc("/headers", headers)

	identify := func(w http.ResponseWriter, r *http.Request) {
		if span, ok := tracer.SpanFromContext(r.Context()); ok {
			tracer.SetUser(
				span, "usr.id", tracer.WithUserEmail("usr.email"),
				tracer.WithUserName("usr.name"), tracer.WithUserSessionID("usr.session_id"),
				tracer.WithUserRole("usr.role"), tracer.WithUserScope("usr.scope"),
			)
		}
		w.Write([]byte("Hello, identify!"))
	}
	mux.HandleFunc("/identify/", identify)
	mux.HandleFunc("/identify", identify)
	mux.HandleFunc("/identify-propagate", func(w http.ResponseWriter, r *http.Request) {
		if span, ok := tracer.SpanFromContext(r.Context()); ok {
			tracer.SetUser(span, "usr.id", tracer.WithPropagation())
		}
		w.Write([]byte("Hello, identify-propagate!"))
	})

	mux.HandleFunc("/user_login_success_event", func(w http.ResponseWriter, r *http.Request) {
		uquery := r.URL.Query()
		uid := "system_tests_user"
		if q := uquery.Get("event_user_id"); q != "" {
			uid = q
		}
		appsec.TrackUserLoginSuccessEvent(r.Context(), uid, map[string]string{"metadata0": "value0", "metadata1": "value1"})
	})

	mux.HandleFunc("/user_login_failure_event", func(w http.ResponseWriter, r *http.Request) {
		uquery := r.URL.Query()
		uid := "system_tests_user"
		if q := uquery.Get("event_user_id"); q != "" {
			uid = q
		}
		exists := true
		if q := uquery.Get("event_user_exists"); q != "" {
			parsed, err := strconv.ParseBool(q)
			if err != nil {
				exists = parsed
			}
		}
		appsec.TrackUserLoginFailureEvent(r.Context(), uid, exists, map[string]string{"metadata0": "value0", "metadata1": "value1"})
	})

	mux.HandleFunc("/custom_event", func(w http.ResponseWriter, r *http.Request) {
		uquery := r.URL.Query()
		name := "system_tests_event"
		if q := uquery.Get("event_name"); q != "" {
			name = q
		}
		appsec.TrackCustomEvent(r.Context(), name, map[string]string{"metadata0": "value0", "metadata1": "value1"})
	})

	mux.HandleFunc("/e2e_single_span", func(w http.ResponseWriter, r *http.Request) {
		parentName := r.URL.Query().Get("parentName")
		childName := r.URL.Query().Get("childName")

		tags := []tracer.StartSpanOption{}

		// We need to propagate the user agent header to retain the mapping between the system-tests/weblog request id
		// and the traces/spans that will be generated below, so that we can reference to them in our tests.
		// See https://github.com/DataDog/system-tests/blob/2d6ae4d5bf87d55855afd36abf36ee710e7d8b3c/utils/interfaces/_core.py#L156
		userAgent := r.UserAgent()
		tags = append(tags, tracer.Tag("http.useragent", userAgent))

		if r.URL.Query().Get("shouldIndex") == "1" {
			tags = append(tags, forceSpanIndexingTags()...)
		}

		// Make a fresh root span!
		duration, _ := time.ParseDuration("10s")
		parentSpan, parentCtx := tracer.StartSpanFromContext(context.Background(), parentName, tags...)
		childSpan, _ := tracer.StartSpanFromContext(parentCtx, childName, tags...)
		childSpan.Finish(tracer.FinishTime(time.Now().Add(duration)))
		parentSpan.Finish(tracer.FinishTime(time.Now().Add(duration * 2)))

		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/read_file", func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Query().Get("file")
		content, err := os.ReadFile(path)

		if err != nil {
			log.Fatalln(err)
			w.WriteHeader(500)
			return
		}
		w.Write([]byte(content))
	})

	mux.HandleFunc("/*", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	initDatadog()
	go listenAndServeGRPC()
	http.ListenAndServe(":7777", mux)
}

func headers(w http.ResponseWriter, r *http.Request) {
	//Data used for header content is irrelevant here, only header presence is checked
	w.Header().Set("Content-Type", "text/plain")
	w.Header().Set("Content-Length", "42")
	w.Header().Set("Content-Language", "en-US")
	w.Write([]byte("Hello, headers!"))
}
