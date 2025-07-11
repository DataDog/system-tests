package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
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

	"github.com/DataDog/dd-trace-go/v2/appsec"
	"github.com/DataDog/dd-trace-go/v2/datastreams"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/opentelemetry"
	"github.com/DataDog/dd-trace-go/v2/ddtrace/tracer"
	"github.com/Shopify/sarama"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
)

func main() {
	// TODO: Update app to use logrus and create /log/library endpoint
	mux := http.NewServeMux()

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

		req, _ := http.NewRequestWithContext(r.Context(), http.MethodGet, url, nil)
		res, err := http.DefaultClient.Do(req)
		if err != nil {
			log.Fatalln("client.Do", err)
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
			log.Fatalln(err)
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
			log.Println("error decoding request body for", r.URL, ":", err)
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
			log.Println("error decoding request body for ", r.URL, ":", err)
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(err.Error()))
			return
		}

		exists, err := strconv.ParseBool(data.Exists)
		if err != nil {
			log.Printf("error parsing exists value %q: %v\n", data.Exists, err)
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

	//orchestrion:ignore
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

		p := opentelemetry.NewTracerProvider()
		oteltracer := p.Tracer("")
		otel.SetTracerProvider(p)
		otel.SetTextMapPropagator(propagation.TraceContext{})
		defer p.ForceFlush(time.Second, func(ok bool) {})

		// Parent span will have the following traits :
		// - spanId of 10000
		// - tags {'attributes':'values'}
		// - tags necessary to retain the mapping between the system-tests/weblog request id and the traces/spans
		// - error tag with 'testing_end_span_options' message
		parentCtx, parentSpan := oteltracer.Start(opentelemetry.ContextWithStartOptions(context.Background(),
			tracer.WithSpanID(10000)), parentName,
			trace.WithAttributes(tags...))
		parentSpan.SetAttributes(attribute.String("attributes", "values"))
		opentelemetry.EndOptions(parentSpan, tracer.WithError(errors.New("testing_end_span_options")))

		// Child span will have the following traits :
		// - tags necessary to retain the mapping between the system-tests/weblog request id and the traces/spans
		// - duration of one second
		// - span kind of SpanKind - Internal
		start := time.Now()
		_, childSpan := oteltracer.Start(parentCtx, childName, trace.WithTimestamp(start), trace.WithAttributes(tags...), trace.WithSpanKind(trace.SpanKindInternal))
		childSpan.End(trace.WithTimestamp(start.Add(time.Second)))
		parentSpan.End()

		w.Write([]byte("OK"))
	})

	//orchestrion:ignore
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

		p := opentelemetry.NewTracerProvider()
		tracer := p.Tracer("")
		otel.SetTracerProvider(p)
		otel.SetTextMapPropagator(propagation.TraceContext{})
		defer p.ForceFlush(time.Second, func(ok bool) {})

		parentCtx, parentSpan := tracer.Start(context.Background(), parentName, trace.WithAttributes(tags...))

		h := otelhttp.NewHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			receivedSpan := trace.SpanFromContext(r.Context())
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
		c := http.Client{Transport: otelhttp.NewTransport(nil, otelhttp.WithSpanOptions(trace.WithAttributes(tags...)))}
		req, err := http.NewRequestWithContext(parentCtx, http.MethodGet, testServer.URL, nil)
		if err != nil {
			log.Fatalln(err)
			w.WriteHeader(500)
			return
		}
		resp, err := c.Do(req)
		_ = resp.Body.Close() // Need to close body to cause otel span to end
		if err != nil {
			log.Fatalln(err)
			w.WriteHeader(500)
			return
		}
		parentSpan.End()

		w.Write([]byte("OK"))
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

	mux.HandleFunc("/requestdownstream", common.Requestdownstream)
	mux.HandleFunc("/returnheaders", common.Returnheaders)

	mux.HandleFunc("/rasp/lfi", rasp.LFI)
	mux.HandleFunc("/rasp/ssrf", rasp.SSRF)
	mux.HandleFunc("/rasp/sqli", rasp.SQLi)

	srv := &http.Server{
		Addr:    ":7777",
		Handler: mux,
	}

	common.InitDatadog()
	go grpc.ListenAndServe()
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

//dd:span span.name:child.span
func write(w http.ResponseWriter, _ *http.Request, d []byte) {
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

	msg := &sarama.ProducerMessage{
		Topic:     topic,
		Partition: 0,
		Value:     sarama.StringEncoder(message),
	}

	partition, offset, err := producer.SendMessage(msg)
	if err != nil {
		return 0, 0, err
	}

	log.Printf("PRODUCER SENT MESSAGE TO (partition offset): %d %d", partition, offset)
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

	partitionConsumer, err := consumer.ConsumePartition(topic, 0, sarama.OffsetOldest)
	if err != nil {
		return "", 0, err
	}
	defer partitionConsumer.Close()

	timeOutTimer := time.NewTimer(time.Duration(timeout) * time.Second)
	defer timeOutTimer.Stop()
	log.Printf("CONSUMING MESSAGES from topic: %s", topic)
	for {
		select {
		case receivedMsg := <-partitionConsumer.Messages():
			responseOutput := fmt.Sprintf("Consumed message.\n\tOffset: %s\n\tMessage: %s\n", fmt.Sprint(receivedMsg.Offset), string(receivedMsg.Value))
			log.Print(responseOutput)
			return responseOutput, 200, nil
		case <-timeOutTimer.C:
			timedOutMessage := "TimeOut"
			log.Print(timedOutMessage)
			return timedOutMessage, 408, nil
		}
	}
}
