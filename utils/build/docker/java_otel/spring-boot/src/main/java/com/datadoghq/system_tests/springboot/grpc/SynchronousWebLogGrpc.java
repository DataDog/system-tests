package com.datadoghq.system_tests.springboot.grpc;

import com.google.protobuf.Value;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public class SynchronousWebLogGrpc implements AutoCloseable {

    private final ManagedChannel channel;
    private final WeblogGrpc.WeblogBlockingStub impl;

    public SynchronousWebLogGrpc(int port) {
        this.channel = ManagedChannelBuilder.forAddress("localhost", port).usePlaintext().build();
        this.impl = WeblogGrpc.newBlockingStub(channel);
    }

    public String unary(String message) {
        Value unary = impl.unary(Value.newBuilder().setStringValue(message).build());
        return unary.getStringValue();
    }

    @Override
    public void close() {
        channel.shutdown();
    }
}
