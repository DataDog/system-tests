package main

import (
	"context"
	"flag"
	"fmt"
	"google.golang.org/grpc"
	"log"
	"net"
)

type apmClientServer struct {
	UnimplementedAPMClientServer
	// spans
}

func (s *apmClientServer) StartSpan(ctx context.Context, args *StartSpanArgs) (*StartSpanReturn, error) {
	return &StartSpanReturn{
		SpanId:  0,
		TraceId: 0,
	}, nil
}

func newServer() *apmClientServer {
	s := &apmClientServer{}
	return s
}

func main() {
	flag.Parse()
	lis, err := net.Listen("tcp", fmt.Sprintf("localhost:%d", 50051))
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	var opts []grpc.ServerOption
	grpcServer := grpc.NewServer(opts...)
	RegisterAPMClientServer(grpcServer, newServer())
	grpcServer.Serve(lis)
}
