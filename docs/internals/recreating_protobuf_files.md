# Recreating protbuf schemas

Protobuf definitions for the traces are taken from https://github.com/DataDog/datadog-agent/tree/master/pkg/trace/pb.

## Dependecies

To recreate them you will need:
    * `protoc`
    * the https://github.com/DataDog/datadog-agent repository
    * `github.com/gogo/protobuf/proto` which is needed by the proto definitions

```sh
git clone https://github.com/DataDog/datadog-agent ~/dd
go get github.com/gogo/protobuf/proto
```

## Generate schema descriptors

```sh
protoc -I $GOPATH/src -I ~/dd/datadog-agent/pkg/trace/pb --include_imports -o utils/interfaces/_decoders/trace_payload.descriptor trace_payload.proto
```
