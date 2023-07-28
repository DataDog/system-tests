
FROM golang:1.18
WORKDIR /client
COPY ./go.mod /client
COPY ./go.sum /client
COPY . /client
RUN go get gopkg.in/DataDog/dd-trace-go.v1@v1.52.0
RUN go install
