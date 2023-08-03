
FROM golang:1.18
WORKDIR /client
COPY ./go.mod /client
COPY ./go.sum /client
COPY . /client
RUN go install
