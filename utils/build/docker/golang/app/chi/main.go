package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"systemtests.weblog/_shared/common"
	"systemtests.weblog/_shared/grpc"
	"systemtests.weblog/_shared/rasp"

	"github.com/go-chi/chi/v5"
	"github.com/sirupsen/logrus"

	chitrace "github.com/DataDog/dd-trace-go/contrib/go-chi/chi.v5/v2"
	httptrace "github.com/DataDog/dd-trace-go/contrib/net/http/v2"
	dd_logrus "github.com/DataDog/dd-trace-go/contrib/sirupsen/logrus/v2"
	"github.com/DataDog/dd-trace-go/v2/appsec"
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

	mux := chi.NewRouter().With(chitrace.Middleware())

	mux.HandleFunc("/stats-unique", func(w http.ResponseWriter, r *http.Request) {
		if c := r.URL.Query().Get("code"); c != "" {
			if code, err := strconv.Atoi(c); err == nil {
				w.WriteHeader(code)
				return
			}
		}
		w.WriteHeader(http.StatusOK)
	})

	mux.HandleFunc("/waf", func(w http.ResponseWriter, r *http.Request) {
		body, err := common.ParseBody(r)
		if err == nil {
			appsec.MonitorParsedHTTPBody(r.Context(), body)
		}
		w.Write([]byte("Hello, WAF!\n"))
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

	mux.HandleFunc("/waf/*", func(w http.ResponseWriter, r *http.Request) {
		body, err := common.ParseBody(r)
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
			tags = append(tags, common.ForceSpanIndexingTags()...)
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
			logrus.Fatalln(err)
			w.WriteHeader(500)
			return
		}
		w.Write([]byte(content))
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

	mux.HandleFunc("/rasp/lfi", rasp.LFI)
	mux.HandleFunc("/rasp/multiple", rasp.LFIMultiple)
	mux.HandleFunc("/rasp/ssrf", rasp.SSRF)
	mux.HandleFunc("/rasp/sqli", rasp.SQLi)

	mux.HandleFunc("/*", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	mux.HandleFunc("/requestdownstream", common.Requestdownstream)
	mux.HandleFunc("/returnheaders", common.Returnheaders)

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

func headers(w http.ResponseWriter, r *http.Request) {
	//Data used for header content is irrelevant here, only header presence is checked
	w.Header().Set("Content-Type", "text/plain")
	w.Header().Set("Content-Length", "42")
	w.Header().Set("Content-Language", "en-US")
	w.Write([]byte("Hello, headers!"))
}
