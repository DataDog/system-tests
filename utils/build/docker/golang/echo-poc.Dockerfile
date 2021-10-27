FROM golang:1

# print versions
RUN go version && curl --version

# install hello world app
RUN mkdir /app
WORKDIR /app

RUN echo 'package main\n\
import (\n\
    "net/http"\n\
    "github.com/labstack/echo/v4"\n\
    "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"\n\
)\n\
func main() {\n\
    e := echo.New()\n\
    \n\
    e.GET("/", hello)\n\
    e.GET("/sample_rate_route/:i", sample_rate_route)\n\
    \n\
    tracer.Start(tracer.WithServiceName("tests"))\n\
    defer tracer.Stop()\n\
    initDatadog()\n\
    \n\
    e.Logger.Fatal(e.Start(":7777"))\n\
}\n\
func hello(c echo.Context) error {\n\
    return c.String(http.StatusOK, "hello world")\n\
}\n\
func sample_rate_route(c echo.Context) error {\n\
    return c.String(http.StatusOK, "hello world")\n\
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
ENV DD_TAGS='env:test, aKey : aVal bKey:bVal cKey:'

# # docker build -f utils/build/docker/golang.echo-poc.Dockerfile -t test .
# # docker run -ti -p 7777:7777 test
