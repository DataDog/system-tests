package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"net/http/httptest"
	"strconv"
	"time"
	"os"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
	oteltrace "go.opentelemetry.io/otel/trace"

	"gopkg.in/DataDog/dd-trace-go.v1/appsec"
	httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"
	ddotel "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/opentelemetry"
	ddtracer "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	ddtracer.Start()
	defer ddtracer.Stop()
	mux := httptrace.NewServeMux()

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

	mux.HandleFunc("/waf", func(w http.ResponseWriter, r *http.Request) {
		body, err := parseBody(r)
		if err == nil {
			appsec.MonitorParsedHTTPBody(r.Context(), body)
		}
		w.Write([]byte("Hello, WAF!\n"))
	})

	mux.HandleFunc("/waf/", func(w http.ResponseWriter, r *http.Request) {
		body, err := parseBody(r)
		if err == nil {
			appsec.MonitorParsedHTTPBody(r.Context(), body)
		}
		write(w, r, []byte("Hello, WAF!"))
	})

	mux.HandleFunc("/users", func(w http.ResponseWriter, r *http.Request) {
		userId := r.URL.Query().Get("user")
		if err := appsec.SetUser(r.Context(), userId); err != nil {
			return
		}
		w.Write([]byte("Hello, user!"))
	})

	mux.HandleFunc("/sample_rate_route/", func(w http.ResponseWriter, r *http.Request) {
		// net/http mux doesn't support advanced patterns, but the given prefix will match any /sample_rate_route/{i}
		w.Write([]byte("OK"))
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

	mux.HandleFunc("/headers", headers)
	mux.HandleFunc("/headers/", headers)

	identify := func(w http.ResponseWriter, r *http.Request) {
		if span, ok := ddtracer.SpanFromContext(r.Context()); ok {
			ddtracer.SetUser(
				span, "usr.id", ddtracer.WithUserEmail("usr.email"),
				ddtracer.WithUserName("usr.name"), ddtracer.WithUserSessionID("usr.session_id"),
				ddtracer.WithUserRole("usr.role"), ddtracer.WithUserScope("usr.scope"),
			)
		}
		w.Write([]byte("Hello, identify!"))
	}
	mux.HandleFunc("/identify/", identify)
	mux.HandleFunc("/identify", identify)
	mux.HandleFunc("/identify-propagate", func(w http.ResponseWriter, r *http.Request) {
		if span, ok := ddtracer.SpanFromContext(r.Context()); ok {
			ddtracer.SetUser(span, "usr.id", ddtracer.WithPropagation())
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

	mux.HandleFunc("/e2e_otel_span", func(w http.ResponseWriter, r *http.Request) {
		parentName := r.URL.Query().Get("parentName")
		childName := r.URL.Query().Get("childName")

		tags := []attribute.KeyValue{}
		// We need to propagate the user agent header to retain the mapping between the system-tests/weblog request id
		// and the traces/spans that will be generated below, so that we can reference to them in our tests.
		// See https://github.com/DataDog/system-tests/blob/2d6ae4d5bf87d55855afd36abf36ee710e7d8b3c/utils/interfaces/_core.py#L156
		userAgent := r.UserAgent()
		tags = append(tags, attribute.String("http.useragent", userAgent))

		if r.URL.Query().Get("shouldIndex") == "1" {
			tags = append(tags,
				attribute.Int("_dd.filter.kept", 1),
				attribute.String("_dd.filter.id", "system_tests_e2e"),
			)
		}

		p := ddotel.NewTracerProvider()
		tracer := p.Tracer("")
		otel.SetTracerProvider(p)
		otel.SetTextMapPropagator(propagation.TraceContext{})
		defer p.ForceFlush(time.Second, func(ok bool) {})

		// Parent span will have the following traits :
		// - spanId of 10000
		// - tags {'attributes':'values'}
		// - tags necessary to retain the mapping between the system-tests/weblog request id and the traces/spans
		// - error tag with 'testing_end_span_options' message
		parentCtx, parentSpan := tracer.Start(ddotel.ContextWithStartOptions(context.Background(),
			ddtracer.WithSpanID(10000)), parentName,
			trace.WithAttributes(tags...))
		parentSpan.SetAttributes(attribute.String("attributes", "values"))
		ddotel.EndOptions(parentSpan, ddtracer.WithError(errors.New("testing_end_span_options")))

		// Child span will have the following traits :
		// - tags necessary to retain the mapping between the system-tests/weblog request id and the traces/spans
		// - duration of one second
		// - span kind of SpanKind - Internal
		start := time.Now()
		_, childSpan := tracer.Start(parentCtx, childName, trace.WithTimestamp(start), trace.WithAttributes(tags...), trace.WithSpanKind(trace.SpanKindInternal))
		childSpan.End(oteltrace.WithTimestamp(start.Add(time.Second)))
		parentSpan.End()

		w.Write([]byte("OK"))
	})

	mux.HandleFunc("/e2e_otel_span/mixed_contrib", func(w http.ResponseWriter, r *http.Request) {
		parentName := r.URL.Query().Get("parentName")

		tags := []attribute.KeyValue{}
		// We need to propagate the user agent header to retain the mapping between the system-tests/weblog request id
		// and the traces/spans that will be generated below, so that we can reference to them in our tests.
		// See https://github.com/DataDog/system-tests/blob/2d6ae4d5bf87d55855afd36abf36ee710e7d8b3c/utils/interfaces/_core.py#L156
		userAgent := r.UserAgent()
		tags = append(tags, attribute.String("http.useragent", userAgent))

		if r.URL.Query().Get("shouldIndex") == "1" {
			tags = append(tags,
				attribute.Int("_dd.filter.kept", 1),
				attribute.String("_dd.filter.id", "system_tests_e2e"),
			)
		}

		p := ddotel.NewTracerProvider()
		tracer := p.Tracer("")
		otel.SetTracerProvider(p)
		otel.SetTextMapPropagator(propagation.TraceContext{})
		defer p.ForceFlush(time.Second, func(ok bool) {})

		parentCtx, parentSpan := tracer.Start(context.Background(), parentName, trace.WithAttributes(tags...))

		h := otelhttp.NewHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			receivedSpan := oteltrace.SpanFromContext(r.Context())
			// Need to propagate the user agent header to retain the mapping between
			// the system-tests/weblog request id and the traces/spans
			receivedSpan.SetAttributes(tags...)
			if receivedSpan.SpanContext().TraceID() != parentSpan.SpanContext().TraceID() {
				log.Fatalln("error in distributed tracing: Datadog OTel API and Otel net/http package span are not connected")
				w.WriteHeader(500)
				return
			}
		}), "testOperation")
		testServer := httptest.NewServer(h)
		defer testServer.Close()

		// Need to propagate the user agent header to retain the mapping between
		// the system-tests/weblog request id and the traces/spans
		c := http.Client{Transport: otelhttp.NewTransport(nil, otelhttp.WithSpanOptions(oteltrace.WithAttributes(tags...)))}
		req, err := http.NewRequestWithContext(parentCtx, http.MethodGet, testServer.URL, nil)
		if err != nil {
			log.Fatalln(err)
			w.WriteHeader(500)
			return
		}
		resp, err := c.Do(req)
		err = resp.Body.Close() // Need to close body to cause otel span to end
		if err != nil {
			log.Fatalln(err)
			w.WriteHeader(500)
			return
		}
		parentSpan.End()

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

	initDatadog()
	go listenAndServeGRPC()
	http.ListenAndServe(":7777", mux)
}

func write(w http.ResponseWriter, r *http.Request, d []byte) {
	span, _ := ddtracer.StartSpanFromContext(r.Context(), "child.span")
	defer span.Finish()
	w.Write(d)
}

func headers(w http.ResponseWriter, r *http.Request) {
	//Data used for header content is irrelevant here, only header presence is checked
	w.Header().Set("content-type", "text/plain")
	w.Header().Set("content-length", "42")
	w.Header().Set("content-language", "en-US")
	w.Write([]byte("Hello, headers!"))
}
