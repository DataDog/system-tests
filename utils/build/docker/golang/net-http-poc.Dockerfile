FROM golang:1

# print versions
RUN go version && curl --version

# install hello world app
WORKDIR /app

RUN echo 'package main\n\
import (\n\
    "net/http"\n\
    "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"\n\
\n\
    httptrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/net/http"\n\
)\n\
func main() {\n\
    tracer.Start(tracer.WithServiceName("tests"))\n\
    defer tracer.Stop()\n\
    mux := httptrace.NewServeMux()\n\
    mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {\n\
		w.Write([]byte("Hello, World!\\n"))\n\
        span, _ := tracer.SpanFromContext(r.Context())\n\
        span.SetTag("http.request.headers.user-agent", r.UserAgent())\n\
	})\n\
    mux.HandleFunc("/sample_rate_route/:i", func(w http.ResponseWriter, r *http.Request) {\n\
		w.Write([]byte("OK"))\n\
	})\n\
    initDatadog()\n\
    http.ListenAndServe(":7777", mux)\n\
}\n\
func initDatadog() {\n\
    span := tracer.StartSpan("init.service")\n\
    defer span.Finish()\n\
    span.SetTag("whip", "done")\n\
}\n' > main.go

COPY utils/build/docker/golang/install_ddtrace.sh binaries* /binaries/
RUN /binaries/install_ddtrace.sh 

CMD ./weblog

# Datadog setup
ENV DD_TRACE_SAMPLE_RATE=0.5
ENV DD_TRACE_DEBUG=true


# # docker build -f utils/build/docker/golang.echo-poc.Dockerfile -t test .
# # docker run -ti -p 7777:7777 test
