package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/http/httptest"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"systemtests.weblog/_shared/common"
	"systemtests.weblog/_shared/grpc"
	"systemtests.weblog/_shared/rasp"

	saramatrace "github.com/DataDog/dd-trace-go/contrib/IBM/sarama/v2"
	"github.com/sirupsen/logrus"

	"github.com/DataDog/dd-trace-go/v2/datastreams"
	"github.com/IBM/sarama"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	otelbaggage "go.opentelemetry.io/otel/baggage"
	"go.opentelemetry.io/otel/propagation"
	oteltrace "go.opentelemetry.io/otel/trace"

	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
	dd_logrus "github.com/DataDog/dd-trace-go/contrib/sirupsen/logrus/v2"
	"github.com/DataDog/dd-trace-go/v2/appsec"
	ddotel "github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/DataDog/dd-trace-go/v2/profiler"
)

func main() {
	logrus.SetFormatter(&logrus.JSONFormatter{})
	logrus.SetOutput(os.Stdout)
	logrus.SetLevel(logrus.DebugLevel)

	// Add Datadog context log hook
	logrus.AddHook(&dd_logrus.DDContextLogHook{})
	tracer.Start()
	defer tracer.Stop()

	err := profiler.Start(
		profiler.WithService("weblog"),
		profiler.WithEnv("system-tests"),
		profiler.WithVersion("1.0"),
		profiler.WithTags(),
		profiler.WithProfileTypes(profiler.CPUProfile, profiler.HeapProfile),
	)

	if err != nil {
		logrus.Fatal(err)
	}
	defer profiler.Stop()

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

	mux.HandleFunc("/stats-unique", func(w http.ResponseWriter, r *http.Request) {
		if c := r.URL.Query().Get("code"); c != "" {
			if code, err := strconv.Atoi(c); err == nil {
				w.WriteHeader(code)
				return
			}
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

	mux.HandleFunc("/waf", func(w http.ResponseWriter, r *http.Request) {
		body, err := common.ParseBody(r)
		if err == nil {
			appsec.MonitorParsedHTTPBody(r.Context(), body)
		}
		w.Write([]byte("Hello, WAF!\n"))
	})

	mux.HandleFunc("/waf/", func(w http.ResponseWriter, r *http.Request) {
		body, err := common.ParseBody(r)
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

	mux.HandleFunc("/tag_value/{tag_value}/{status_code}", func(w http.ResponseWriter, r *http.Request) {
		tag := r.PathValue("tag_value")
		status, _ := strconv.Atoi(r.PathValue("status_code"))
		span, _ := tracer.SpanFromContext(r.Context())
		span.SetTag("appsec.events.system_tests_appsec_event.value", tag)
		for key, values := range r.URL.Query() {
			for _, value := range values {
				w.Header().Add(key, value)
			}
		}
		w.WriteHeader(status)
		w.Write([]byte("Value tagged"))

		switch {
		case r.Header.Get("Content-Type") == "application/json":
			body, _ := io.ReadAll(r.Body)
			var bodyMap map[string]any
			if err := json.Unmarshal(body, &bodyMap); err == nil {
				appsec.MonitorParsedHTTPBody(r.Context(), bodyMap)
			}
		case r.ParseForm() == nil:
			appsec.MonitorParsedHTTPBody(r.Context(), r.PostForm)
		}
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
		url := r.URL.Query().Get("url")
		if url == "" {
			w.Write([]byte("OK"))
			return
		}

		client := httptrace.WrapClient(http.DefaultClient)
		req, _ := http.NewRequestWithContext(r.Context(), http.MethodGet, url, nil)
		res, err := client.Do(req)
		if err != nil {
			logrus.Fatalln("client.Do", err)
		}

		defer res.Body.Close()

		requestHeaders := make(map[string]string, len(req.Header))
		for key, values := range req.Header {
			requestHeaders[key] = strings.Join(values, ",")
		}

		responseHeaders := make(map[string]string, len(res.Header))
		for key, values := range res.Header {
			responseHeaders[key] = strings.Join(values, ",")
		}

		jsonResponse, err := json.Marshal(struct {
			URL             string            `json:"url"`
			StatusCode      int               `json:"status_code"`
			RequestHeaders  map[string]string `json:"request_headers"`
			ResponseHeaders map[string]string `json:"response_headers"`
		}{URL: url, StatusCode: res.StatusCode, RequestHeaders: requestHeaders, ResponseHeaders: responseHeaders})
		if err != nil {
			logrus.Fatalln(err)
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write(jsonResponse)
	})

	mux.HandleFunc("/headers", headers)
	mux.HandleFunc("/headers/", headers)

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

	mux.HandleFunc("/kafka/produce", func(w http.ResponseWriter, r *http.Request) {
		var message = "Test"

		topic := r.URL.Query().Get("topic")
		if len(topic) == 0 {
			w.Write([]byte("missing param 'topic'"))
			w.WriteHeader(422)
			return
		}

		_, _, err := kafkaProduce(topic, message)
		if err != nil {
			w.Write([]byte(err.Error()))
			w.WriteHeader(500)
			return
		}

		w.Write([]byte("OK"))
		w.WriteHeader(200)
	})

	mux.HandleFunc("/kafka/consume", func(w http.ResponseWriter, r *http.Request) {
		topic := r.URL.Query().Get("topic")
		if len(topic) == 0 {
			w.Write([]byte("missing param 'topic'"))
			w.WriteHeader(422)
			return
		}

		timeout, err := strconv.ParseInt(r.URL.Query().Get("timeout"), 10, 0)
		if err != nil {
			timeout = 20
		}

		message, status, err := kafkaConsume(topic, timeout)
		if err != nil {
			panic(err)
		}

		w.Write([]byte(message))
		w.WriteHeader(status)
	})

	mux.HandleFunc("/user_login_success_event", func(w http.ResponseWriter, r *http.Request) {
		uquery := r.URL.Query()
		uid := "system_tests_user"
		if q := uquery.Get("event_user_id"); q != "" {
			uid = q
		}
		appsec.TrackUserLoginSuccessEvent(r.Context(), uid, map[string]string{"metadata0": "value0", "metadata1": "value1"})
	})

	mux.HandleFunc("/user_login_success_event_v2", func(w http.ResponseWriter, r *http.Request) {
		var data struct {
			Login    string            `json:"login"`
			UserID   string            `json:"user_id"`
			Metadata map[string]string `json:"metadata"`
		}
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			logrus.Println("error decoding request body for", r.URL, ":", err)
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(err.Error()))
			return
		}

		appsec.TrackUserLoginSuccess(r.Context(), data.Login, data.UserID, data.Metadata)
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

	mux.HandleFunc("/user_login_failure_event_v2", func(w http.ResponseWriter, r *http.Request) {
		var data struct {
			Login    string            `json:"login"`
			Exists   string            `json:"exists"`
			Metadata map[string]string `json:"metadata"`
		}
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			logrus.Println("error decoding request body for ", r.URL, ":", err)
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(err.Error()))
			return
		}

		exists, err := strconv.ParseBool(data.Exists)
		if err != nil {
			logrus.Printf("error parsing exists value %q: %v\n", data.Exists, err)
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(err.Error()))
			return
		}

		appsec.TrackUserLoginFailure(r.Context(), data.Login, exists, data.Metadata)
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
		otracer := p.Tracer("")
		otel.SetTracerProvider(p)
		otel.SetTextMapPropagator(propagation.TraceContext{})
		defer p.ForceFlush(time.Second, func(ok bool) {})

		// Parent span will have the following traits :
		// - spanId of 10000
		// - tags {'attributes':'values'}
		// - tags necessary to retain the mapping between the system-tests/weblog request id and the traces/spans
		// - error tag with 'testing_end_span_options' message
		parentCtx, parentSpan := otracer.Start(ddotel.ContextWithStartOptions(context.Background(),
			tracer.WithSpanID(10000)), parentName,
			oteltrace.WithAttributes(tags...))
		parentSpan.SetAttributes(attribute.String("attributes", "values"))
		ddotel.EndOptions(parentSpan, tracer.WithError(errors.New("testing_end_span_options")))

		// Child span will have the following traits :
		// - tags necessary to retain the mapping between the system-tests/weblog request id and the traces/spans
		// - duration of one second
		// - span kind of SpanKind - Internal
		start := time.Now()
		_, childSpan := otracer.Start(parentCtx, childName, oteltrace.WithTimestamp(start), oteltrace.WithAttributes(tags...), oteltrace.WithSpanKind(oteltrace.SpanKindInternal))
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

		parentCtx, parentSpan := tracer.Start(context.Background(), parentName, oteltrace.WithAttributes(tags...))

		h := otelhttp.NewHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			receivedSpan := oteltrace.SpanFromContext(r.Context())
			// Need to propagate the user agent header to retain the mapping between
			// the system-tests/weblog request id and the traces/spans
			receivedSpan.SetAttributes(tags...)
			if receivedSpan.SpanContext().TraceID() != parentSpan.SpanContext().TraceID() {
				logrus.Fatalln("error in distributed tracing: Datadog OTel API and Otel net/http package span are not connected")
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
			logrus.Fatalln(err)
			w.WriteHeader(500)
			return
		}
		resp, err := c.Do(req)
		_ = resp.Body.Close() // Need to close body to cause otel span to end
		if err != nil {
			logrus.Fatalln(err)
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
			logrus.Fatalln(err)
			w.WriteHeader(500)
			return
		}
		w.Write([]byte(content))
	})

	mux.HandleFunc("/dsm", func(w http.ResponseWriter, r *http.Request) {
		var message = "Test DSM Context Propagation"

		integration := r.URL.Query().Get("integration")
		if len(integration) == 0 {
			w.WriteHeader(422)
			w.Write([]byte("missing param 'integration'"))
			return
		}

		if integration == "kafka" {
			queue := r.URL.Query().Get("queue")
			if len(queue) == 0 {
				w.WriteHeader(422)
				w.Write([]byte("missing param 'queue' for kafka dsm"))
				return
			}

			_, _, err := kafkaProduce(queue, message)
			if err != nil {
				w.WriteHeader(500)
				w.Write([]byte(err.Error()))
				return
			}

			timeout, err := strconv.ParseInt(r.URL.Query().Get("timeout"), 10, 0)
			if err != nil {
				timeout = 20
			}

			_, _, err = kafkaConsume(queue, timeout)
			if err != nil {
				w.WriteHeader(500)
				w.Write([]byte(err.Error()))
				return
			}
		}

		w.WriteHeader(200)
		w.Write([]byte("ok"))
	})

	mux.HandleFunc("/dsm/inject", func(w http.ResponseWriter, r *http.Request) {
		topic := r.URL.Query().Get("topic")
		if len(topic) == 0 {
			w.WriteHeader(422)
			w.Write([]byte("missing param 'topic'"))
			return
		}
		intType := r.URL.Query().Get("integration")
		if len(intType) == 0 {
			w.WriteHeader(422)
			w.Write([]byte("missing param 'integration'"))
			return
		}

		edges := []string{"direction:out", "topic:" + topic, "type:" + intType}
		carrier := make(carrier)
		ctx := context.Background()
		ctx, ok := tracer.SetDataStreamsCheckpoint(ctx, edges...)
		if !ok {
			w.WriteHeader(422)
			w.Write([]byte("failed to create DSM checkpoint"))
			return
		}
		datastreams.InjectToBase64Carrier(ctx, carrier)

		jsonData, err := json.Marshal(carrier)
		if err != nil {
			w.WriteHeader(422)
			w.Write([]byte("failed to convert carrier to JSON"))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		w.Write(jsonData)
	})

	mux.HandleFunc("/dsm/extract", func(w http.ResponseWriter, r *http.Request) {
		topic := r.URL.Query().Get("topic")
		if len(topic) == 0 {
			w.WriteHeader(422)
			w.Write([]byte("missing param 'topic'"))
			return
		}
		intType := r.URL.Query().Get("integration")
		if len(intType) == 0 {
			w.WriteHeader(422)
			w.Write([]byte("missing param 'integration'"))
			return
		}
		rawCtx := r.URL.Query().Get("ctx")
		if len(rawCtx) == 0 {
			w.WriteHeader(422)
			w.Write([]byte("missing param 'ctx'"))
			return
		}
		carrier := make(carrier)
		err := json.Unmarshal([]byte(rawCtx), &carrier)
		if err != nil {
			w.WriteHeader(422)
			w.Write([]byte("failed to parse JSON"))
			return
		}

		edges := []string{"direction:in", "topic:" + topic, "type:" + intType}
		ctx := datastreams.ExtractFromBase64Carrier(context.Background(), carrier)
		_, ok := tracer.SetDataStreamsCheckpoint(ctx, edges...)
		if !ok {
			w.WriteHeader(422)
			w.Write([]byte("failed to create DSM checkpoint"))
			return
		}

		w.WriteHeader(200)
		w.Write([]byte("ok"))
	})

	mux.HandleFunc("/otel_drop_in_default_propagator_extract", func(w http.ResponseWriter, r *http.Request) {
		// Differing from other languages, the user must set the text map propagator because dd-trace-go
		// doesn't automatically instrument at runtime (not including Orchestrion)
		otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))

		httpCarrier := HttpCarrier{header: r.Header}

		propagator := otel.GetTextMapPropagator()
		ctx := propagator.Extract(r.Context(), httpCarrier)

		spanContext := oteltrace.SpanContextFromContext(ctx)
		baggage := otelbaggage.FromContext(ctx)

		base := 16
		bitSize := 64
		result := make(map[string]any, 4)

		num, err := strconv.ParseInt(spanContext.TraceID().String()[16:], base, bitSize)
		if err == nil {
			result["trace_id"] = num
		}

		num, err = strconv.ParseInt(spanContext.SpanID().String(), base, bitSize)
		if err == nil {
			result["span_id"] = num
		}

		result["tracestate"] = spanContext.TraceState().String()
		result["baggage"] = baggage.String()

		jsonData, err := json.Marshal(result)
		if err != nil {
			w.WriteHeader(422)
			w.Write([]byte("failed to convert carrier to JSON"))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		w.Write(jsonData)
	})

	mux.HandleFunc("/otel_drop_in_default_propagator_inject", func(w http.ResponseWriter, r *http.Request) {
		// Differing from other languages, the user must set the text map propagator because dd-trace-go
		// doesn't automatically instrument at runtime (not including Orchestrion)
		otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))

		ctx := context.Background()
		p := ddotel.NewTracerProvider()
		tracer := p.Tracer("")
		otel.SetTracerProvider(p)

		_, span := tracer.Start(ddotel.ContextWithStartOptions(ctx), "main")
		newCtx := oteltrace.ContextWithSpan(ctx, span)

		propagator := otel.GetTextMapPropagator()
		mapCarrier := make(MapCarrier)
		propagator.Inject(newCtx, mapCarrier)

		jsonData, err := json.Marshal(mapCarrier)
		span.End()

		if err != nil {
			w.WriteHeader(422)
			w.Write([]byte("failed to convert carrier to JSON"))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		w.Write(jsonData)
	})

	mux.HandleFunc("/session/new", func(w http.ResponseWriter, r *http.Request) {
		sessionID := strconv.Itoa(rand.Int())
		w.Header().Add("Set-Cookie", "session="+sessionID+"; Path=/; Max-Age=3600; Secure; HttpOnly")
	})

	mux.HandleFunc("/session/user", func(w http.ResponseWriter, r *http.Request) {
		user := r.URL.Query().Get("sdk_user")
		cookie, err := r.Cookie("session")
		if err != nil {
			w.WriteHeader(500)
			w.Write([]byte("missing session cookie"))
		}
		appsec.TrackUserLoginSuccessEvent(r.Context(), user, map[string]string{}, tracer.WithUserSessionID(cookie.Value))
	})

	mux.HandleFunc("/inferred-proxy/span-creation", func(w http.ResponseWriter, r *http.Request) {
		statusCodeStr := r.URL.Query().Get("status_code")
		statusCode := 200
		if statusCodeStr != "" {
			var err error
			statusCode, err = strconv.Atoi(statusCodeStr)
			if err != nil {
				statusCode = 400 // Bad request if conversion fails
			}
		}

		// Log the request headers
		fmt.Println("Received an API Gateway request")
		for key, values := range r.Header {
			for _, value := range values {
				fmt.Printf("%s: %s\n", key, value)
			}
		}

		// Send the response
		w.WriteHeader(statusCode)
		w.Write([]byte("ok"))
	})

	mux.HandleFunc("/log/library", func(w http.ResponseWriter, r *http.Request) {
		msg := r.URL.Query().Get("msg")
		if msg == "" {
			msg = "msg"
		}
		ctx := r.Context()
		switch r.URL.Query().Get("level") {
		case "warn":
			logrus.WithContext(ctx).Warn(msg)
		case "error":
			logrus.WithContext(ctx).Error(msg)
		case "debug":
			logrus.WithContext(ctx).Debug(msg)
		default:
			logrus.WithContext(ctx).Info(msg)
		}
		w.WriteHeader(200)
		w.Write([]byte("ok"))
	})

	mux.HandleFunc("/requestdownstream", common.Requestdownstream)
	mux.HandleFunc("/returnheaders", common.Returnheaders)

	mux.HandleFunc("/rasp/lfi", rasp.LFI)
	mux.HandleFunc("/rasp/multiple", rasp.LFIMultiple)
	mux.HandleFunc("/rasp/ssrf", rasp.SSRF)
	mux.HandleFunc("/rasp/sqli", rasp.SQLi)

	mux.HandleFunc("/add_event", func(w http.ResponseWriter, r *http.Request) {
		span, ok := tracer.SpanFromContext(r.Context())
		if !ok {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`span not found in context`))
			return
		}
		span.AddEvent("span.event", tracer.WithSpanEventAttributes(map[string]any{
			"string": "value",
			"int":    1,
		}))
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`[Event added]`))
	})

	mux.HandleFunc("/debugger/log", logProbe)
	mux.HandleFunc("/debugger/mix", mixProbe)

	srv := &http.Server{
		Addr:    ":7777",
		Handler: mux,
	}

	common.InitDatadog()
	go grpc.ListenAndServe()
	go func() {
		if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			logrus.Fatal(err)
		}
	}()

	c := make(chan os.Signal, 1)
	signal.Notify(c, syscall.SIGTERM)
	<-c

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		logrus.Fatalf("HTTP shutdown error: %v", err)
	}
}

type carrier map[string]string

func (c carrier) Set(key, val string) {
	c[key] = val
}

func (c carrier) ForeachKey(handler func(key, val string) error) error {
	for k, v := range c {
		if err := handler(k, v); err != nil {
			return err
		}
	}
	return nil
}

type MapCarrier map[string]string

func (c MapCarrier) Get(key string) string {
	return c[key]
}

func (c MapCarrier) Set(key, val string) {
	c[key] = val
}

func (c MapCarrier) Keys() []string {
	keys := make([]string, 0, len(c))
	for k := range c {
		keys = append(keys, k)
	}
	return keys
}

type HttpCarrier struct {
	header http.Header
}

func (c HttpCarrier) Get(key string) string {
	return c.header.Get(key)
}

func (c HttpCarrier) Set(key, val string) {
	c.header.Set(key, val)
}

func (c HttpCarrier) Keys() []string {
	keys := make([]string, 0, len(c.header))
	for k := range c.header {
		keys = append(keys, k)
	}
	return keys
}

func write(w http.ResponseWriter, r *http.Request, d []byte) {
	span, _ := tracer.StartSpanFromContext(r.Context(), "child.span")
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

func kafkaProduce(topic, message string) (int32, int64, error) {
	var server = "kafka:9092"

	cfg := sarama.NewConfig()
	cfg.Producer.Return.Successes = true

	producer, err := sarama.NewSyncProducer([]string{server}, cfg)
	if err != nil {
		return 0, 0, err
	}
	defer producer.Close()

	producer = saramatrace.WrapSyncProducer(cfg, producer, saramatrace.WithDataStreams())

	msg := &sarama.ProducerMessage{
		Topic:     topic,
		Partition: 0,
		Value:     sarama.StringEncoder(message),
	}

	partition, offset, err := producer.SendMessage(msg)
	if err != nil {
		return 0, 0, err
	}

	logrus.Printf("PRODUCER SENT MESSAGE TO (partition offset): %d %d", partition, offset)
	return partition, offset, nil
}

func kafkaConsume(topic string, timeout int64) (string, int, error) {
	var server = "kafka:9092"
	cfg := sarama.NewConfig()

	consumer, err := sarama.NewConsumer([]string{server}, cfg)
	if err != nil {
		return "", 0, err
	}
	defer consumer.Close()

	consumer = saramatrace.WrapConsumer(consumer, saramatrace.WithDataStreams())
	partitionConsumer, err := consumer.ConsumePartition(topic, 0, sarama.OffsetOldest)
	if err != nil {
		return "", 0, err
	}
	defer partitionConsumer.Close()

	timeOutTimer := time.NewTimer(time.Duration(timeout) * time.Second)
	defer timeOutTimer.Stop()
	logrus.Printf("CONSUMING MESSAGES from topic: %s", topic)
	for {
		select {
		case receivedMsg := <-partitionConsumer.Messages():
			responseOutput := fmt.Sprintf("Consumed message.\n\tOffset: %s\n\tMessage: %s\n", fmt.Sprint(receivedMsg.Offset), string(receivedMsg.Value))
			logrus.Print(responseOutput)
			return responseOutput, 200, nil
		case <-timeOutTimer.C:
			timedOutMessage := "TimeOut"
			logrus.Print(timedOutMessage)
			return timedOutMessage, 408, nil
		}
	}
}

// The below handler functions are used to test the live debugging feature.
// They need to be free-standing functions to avoid inlining and to make sure
// make sure the debugger can probe them.

func logProbe(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte("Log probe"))
}

func mixProbe(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte("Mix probe"))
}
