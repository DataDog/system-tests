module systemtests.weblog

go 1.25.0

require (
	github.com/99designs/gqlgen v0.17.83
	github.com/DataDog/dd-trace-go/contrib/99designs/gqlgen/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/IBM/sarama/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/database/sql/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/gin-gonic/gin/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/go-chi/chi.v5/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/google.golang.org/grpc/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/graph-gophers/graphql-go/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/graphql-go/graphql/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/labstack/echo.v4/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/labstack/echo.v5/v2 v2.0.0-20260608223758-cfe2935ff187
	github.com/DataDog/dd-trace-go/contrib/net/http/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/contrib/sirupsen/logrus/v2 v2.7.0-dev
	github.com/DataDog/dd-trace-go/v2 v2.10.0-dev
	github.com/IBM/sarama v1.46.2
	github.com/gin-gonic/gin v1.10.1
	github.com/go-chi/chi/v5 v5.2.2
	github.com/graph-gophers/graphql-go v1.5.0
	github.com/graphql-go/graphql v0.8.1
	github.com/graphql-go/handler v0.2.3
	github.com/labstack/echo/v4 v4.11.1
	github.com/labstack/echo/v5 v5.1.0
	github.com/lib/pq v1.10.2
	github.com/mattn/go-sqlite3 v1.14.32
	github.com/open-feature/go-sdk v1.17.0
	github.com/sirupsen/logrus v1.9.3
	github.com/vektah/gqlparser/v2 v2.5.31
	go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.68.0
	go.opentelemetry.io/otel v1.43.0
	go.opentelemetry.io/otel/trace v1.43.0
	google.golang.org/grpc v1.80.0
	google.golang.org/protobuf v1.36.11
)

require (
	github.com/DataDog/datadog-agent/comp/core/tagger/origindetection v0.79.0 // indirect
	github.com/DataDog/datadog-agent/pkg/obfuscate v0.79.0 // indirect
	github.com/DataDog/datadog-agent/pkg/opentelemetry-mapping-go/otlp/attributes v0.79.0 // indirect
	github.com/DataDog/datadog-agent/pkg/proto v0.79.0 // indirect
	github.com/DataDog/datadog-agent/pkg/remoteconfig/state v0.79.0 // indirect
	github.com/DataDog/datadog-agent/pkg/trace v0.79.0 // indirect
	github.com/DataDog/datadog-agent/pkg/trace/log v0.79.0 // indirect
	github.com/DataDog/datadog-agent/pkg/trace/stats v0.79.0 // indirect
	github.com/DataDog/datadog-agent/pkg/trace/traceutil v0.79.0 // indirect
	github.com/DataDog/datadog-go/v5 v5.8.3 // indirect
	github.com/DataDog/go-libddwaf/v4 v4.9.0 // indirect
	github.com/DataDog/go-runtime-metrics-internal v0.0.4-0.20260217080614-b0f4edc38a6d // indirect
	github.com/DataDog/go-sqllexer v0.2.1 // indirect
	github.com/DataDog/go-tuf v1.1.1-0.5.2 // indirect
	github.com/DataDog/sketches-go v1.4.8 // indirect
	github.com/Microsoft/go-winio v0.6.2 // indirect
	github.com/agnivade/levenshtein v1.2.1 // indirect
	github.com/bytedance/sonic v1.12.0 // indirect
	github.com/bytedance/sonic/loader v0.2.0 // indirect
	github.com/cenkalti/backoff/v5 v5.0.3 // indirect
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/cihub/seelog v0.0.0-20170130134532-f561c5e57575 // indirect
	github.com/cloudwego/base64x v0.1.4 // indirect
	github.com/cloudwego/iasm v0.2.0 // indirect
	github.com/davecgh/go-spew v1.1.2-0.20180830191138-d8f796af33cc // indirect
	github.com/dustin/go-humanize v1.0.1 // indirect
	github.com/eapache/go-resiliency v1.7.0 // indirect
	github.com/eapache/go-xerial-snappy v0.0.0-20230731223053-c322873962e3 // indirect
	github.com/eapache/queue v1.1.0 // indirect
	github.com/ebitengine/purego v0.10.0 // indirect
	github.com/felixge/httpsnoop v1.0.4 // indirect
	github.com/gabriel-vasile/mimetype v1.4.3 // indirect
	github.com/gin-contrib/sse v0.1.0 // indirect
	github.com/go-logr/logr v1.4.3 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	github.com/go-ole/go-ole v1.3.0 // indirect
	github.com/go-playground/locales v0.14.1 // indirect
	github.com/go-playground/universal-translator v0.18.1 // indirect
	github.com/go-playground/validator/v10 v10.20.0 // indirect
	github.com/go-viper/mapstructure/v2 v2.5.0 // indirect
	github.com/goccy/go-json v0.10.2 // indirect
	github.com/golang/snappy v0.0.4 // indirect
	github.com/google/pprof v0.0.0-20250403155104-27863c87afa6 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/gorilla/websocket v1.5.0 // indirect
	github.com/grpc-ecosystem/grpc-gateway/v2 v2.28.0 // indirect
	github.com/hashicorp/errwrap v1.1.0 // indirect
	github.com/hashicorp/go-multierror v1.1.1 // indirect
	github.com/hashicorp/go-uuid v1.0.3 // indirect
	github.com/hashicorp/go-version v1.9.0 // indirect
	github.com/hashicorp/golang-lru/v2 v2.0.7 // indirect
	github.com/jcmturner/aescts/v2 v2.0.0 // indirect
	github.com/jcmturner/dnsutils/v2 v2.0.0 // indirect
	github.com/jcmturner/gofork v1.7.6 // indirect
	github.com/jcmturner/gokrb5/v8 v8.4.4 // indirect
	github.com/jcmturner/rpc/v2 v2.0.3 // indirect
	github.com/json-iterator/go v1.1.12 // indirect
	github.com/klauspost/compress v1.18.6 // indirect
	github.com/klauspost/cpuid/v2 v2.3.0 // indirect
	github.com/labstack/gommon v0.4.2 // indirect
	github.com/leodido/go-urn v1.4.0 // indirect
	github.com/linkdata/deadlock v0.5.5 // indirect
	github.com/lufia/plan9stats v0.0.0-20260216142805-b3301c5f2a88 // indirect
	github.com/mattn/go-colorable v0.1.14 // indirect
	github.com/mattn/go-isatty v0.0.20 // indirect
	github.com/minio/simdjson-go v0.4.5 // indirect
	github.com/modern-go/concurrent v0.0.0-20180306012644-bacd9c7ef1dd // indirect
	github.com/modern-go/reflect2 v1.0.3-0.20250322232337-35a7c28c31ee // indirect
	github.com/outcaste-io/ristretto v0.2.3 // indirect
	github.com/pelletier/go-toml/v2 v2.2.2 // indirect
	github.com/petermattis/goid v0.0.0-20260226131333-17d1149c6ac6 // indirect
	github.com/philhofer/fwd v1.2.0 // indirect
	github.com/pierrec/lz4/v4 v4.1.22 // indirect
	github.com/pkg/errors v0.9.1 // indirect
	github.com/planetscale/vtprotobuf v0.6.1-0.20240319094008-0393e58bdf10 // indirect
	github.com/power-devops/perfstat v0.0.0-20240221224432-82ca36839d55 // indirect
	github.com/puzpuzpuz/xsync/v3 v3.5.1 // indirect
	github.com/rcrowley/go-metrics v0.0.0-20250401214520-65e299d6c5c9 // indirect
	github.com/richardartoul/molecule v1.0.1-0.20240531184615-7ca0df43c0b3 // indirect
	github.com/secure-systems-lab/go-securesystemslib v0.10.0 // indirect
	github.com/shirou/gopsutil/v4 v4.26.3 // indirect
	github.com/sosodev/duration v1.3.1 // indirect
	github.com/spaolacci/murmur3 v1.1.0 // indirect
	github.com/tinylib/msgp v1.6.3 // indirect
	github.com/tklauser/go-sysconf v0.3.16 // indirect
	github.com/tklauser/numcpus v0.11.0 // indirect
	github.com/trailofbits/go-mutexasserts v0.0.0-20250514102930-c1f3d2e37561 // indirect
	github.com/twitchyliquid64/golang-asm v0.15.1 // indirect
	github.com/ugorji/go/codec v1.2.12 // indirect
	github.com/valyala/bytebufferpool v1.0.0 // indirect
	github.com/valyala/fasttemplate v1.2.2 // indirect
	github.com/yusufpapurcu/wmi v1.2.4 // indirect
	go.opentelemetry.io/auto/sdk v1.2.1 // indirect
	go.opentelemetry.io/collector/component v1.56.0 // indirect
	go.opentelemetry.io/collector/featuregate v1.56.0 // indirect
	go.opentelemetry.io/collector/pdata v1.56.0 // indirect
	go.opentelemetry.io/collector/pdata/pprofile v0.150.0 // indirect
	go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc v1.43.0 // indirect
	go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp v1.43.0 // indirect
	go.opentelemetry.io/otel/metric v1.43.0 // indirect
	go.opentelemetry.io/otel/sdk v1.43.0 // indirect
	go.opentelemetry.io/otel/sdk/metric v1.43.0 // indirect
	go.opentelemetry.io/proto/otlp v1.10.0 // indirect
	go.uber.org/atomic v1.11.0 // indirect
	go.uber.org/mock v0.6.0 // indirect
	go.uber.org/multierr v1.11.0 // indirect
	go.uber.org/zap v1.27.1 // indirect
	go.yaml.in/yaml/v3 v3.0.4 // indirect
	golang.org/x/arch v0.8.0 // indirect
	golang.org/x/crypto v0.52.0 // indirect
	golang.org/x/exp v0.0.0-20260209203927-2842357ff358 // indirect
	golang.org/x/mod v0.35.0 // indirect
	golang.org/x/net v0.55.0 // indirect
	golang.org/x/sys v0.45.0 // indirect
	golang.org/x/text v0.37.0 // indirect
	golang.org/x/time v0.15.0 // indirect
	golang.org/x/xerrors v0.0.0-20240903120638-7835f813f4da // indirect
	google.golang.org/genproto/googleapis/api v0.0.0-20260406210006-6f92a3bedf2d // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20260406210006-6f92a3bedf2d // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)
