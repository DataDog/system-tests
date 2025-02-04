package com.datadoghq.system_tests.springboot.grpc;

import com.google.protobuf.Value;
import io.grpc.stub.StreamObserver;

public class Responder extends WeblogGrpc.WeblogImplBase {
  @Override
  public void unary(Value request, StreamObserver<Value> responseObserver) {
    responseObserver.onNext(Value.newBuilder().setStringValue("hello " + request.getStringValue()).build());
    responseObserver.onCompleted();
  }
}
