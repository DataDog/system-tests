package main

import (
	"net/http"

	"gopkg.in/DataDog/dd-trace-go.v1/appsec"
	httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

var tufRoot = `{"signed":{"_type":"root","spec_version":"1.0","version":1,"expires":"2032-05-29T12:49:41.030418-04:00","keys":{"ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e":{"keytype":"ed25519","scheme":"ed25519","keyid_hash_algorithms":["sha256","sha512"],"keyval":{"public":"7d3102e39abe71044d207550bda239c71380d013ec5a115f79f51622630054e6"}}},"roles":{"root":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"snapshot":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"targets":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"timestsmp":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1}},"consistent_snapshot":true},"signatures":[{"keyid":"ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e","sig":"d7e24828d1d3104e48911860a13dd6ad3f4f96d45a9ea28c4a0f04dbd3ca6c205ed406523c6c4cacfb7ebba68f7e122e42746d1c1a83ffa89c8bccb6f7af5e06"}]}`

func main() {
	tracer.Start(
		tracer.WithServiceVersion("1.2.3"),
		tracer.WithRemoteConfigTUFRoot(tufRoot),
	)
	defer tracer.Stop()
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

	mux.HandleFunc("/sample_rate_route/:i", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
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

	initDatadog()
	go listenAndServeGRPC()
	http.ListenAndServe(":7777", mux)
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
