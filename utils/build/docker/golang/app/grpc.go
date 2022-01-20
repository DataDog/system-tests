package main

import (
	"context"
	"log"
	"net"
	"net/http"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/types/known/structpb"

	grpctrace "gopkg.in/DataDog/dd-trace-go.v1/contrib/google.golang.org/grpc"
	"gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

func main() {
	tracer.Start()
	defer tracer.Stop()

	lis, err := net.Listen("tcp", ":7778")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	grpcServer := grpc.NewServer(
		grpc.UnaryInterceptor(grpctrace.UnaryServerInterceptor(grpctrace.WithRequestTags())),
		grpc.StreamInterceptor(grpctrace.StreamServerInterceptor()),
		grpc.Creds(insecure.NewCredentials()),
	)
	RegisterWeblogServer(grpcServer, server{})

	httpapi := NewWeblogMux()

	initDatadog()
	go func() {
		err := grpcServer.Serve(lis)
		if err != nil {
			log.Fatal(err)
		}
	}()

	http.ListenAndServe(":7777", httpapi)
}

type server struct {
	UnimplementedWeblogServer
}

func (s server) Unary(ctx context.Context, req *structpb.Value) (*structpb.Value, error) {
	return structpb.NewStringValue("hello from Go"), nil
}

func (s server) ServerStream(req *structpb.Value, stream Weblog_ServerStreamServer) error {
	//TODO implement me
	panic("implement me")
}

func (s server) ClientStream(stream Weblog_ClientStreamServer) error {
	//TODO implement me
	panic("implement me")
}

func (s server) Bidi(stream Weblog_BidiServer) error {
	//TODO implement me
	panic("implement me")
}
