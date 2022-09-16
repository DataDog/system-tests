
FROM golang:1.18
WORKDIR /client
COPY go.mod /client
COPY go.sum /client
RUN go mod download
COPY . /client
RUN go get gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer
RUN go install
