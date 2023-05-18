'use strict'

const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const Servicer = require('./servicer')

const PROTO_PATH = 'apm_test_client.proto';
const PORT = process.env.APM_TEST_CLIENT_SERVER_PORT;

const options = {
    keepCase: true,
    logs: String,
    enums: String,
    defaults: true,
    oneofs: true
};

const packageDef = protoLoader.loadSync(PROTO_PATH, options);

const grpcObj = grpc.loadPackageDefinition(packageDef);

const server = new grpc.Server();
const servicer = new Servicer();

server.addService(grpcObj.APMClient.service, {
    StartSpan: servicer.StartSpan,
    InjectHeaders: servicer.InjectHeaders,
    SpanSetMeta: servicer.SetTag,
    SpanSetMetric: servicer.SetTag, // dd-trace-js has support for numeric values in tags
    SpanSetError: servicer.SpanSetError,
    FinishSpan: servicer.FinishSpan,
    FlushSpans: servicer.FlushSpans,
    FlushTraceStats: servicer.FlushTraceStats,
    StopTracer: servicer.StopTracer
});

server.bindAsync(
    `[::]:${PORT}`,
    grpc.ServerCredentials.createInsecure(),
    (error, port) => {
        if (error) {
            console.error(error);
            throw error;
        }
        console.log(`Server running on port ${port}`);
        server.start();
    }
);
