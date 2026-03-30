<?php

declare(strict_types=1);

use OpenTelemetry\SDK\Common\Export\TransportFactoryInterface;
use OpenTelemetry\SDK\Common\Export\TransportInterface;
use OpenTelemetry\SDK\Common\Future\CancellationInterface;
use OpenTelemetry\SDK\Common\Future\CompletedFuture;
use OpenTelemetry\SDK\Common\Future\ErrorFuture;
use OpenTelemetry\SDK\Common\Future\FutureInterface;
use Opentelemetry\Proto\Collector\Logs\V1\ExportLogsServiceRequest;
use Opentelemetry\Proto\Collector\Logs\V1\LogsServiceClient;

/**
 * Minimal synchronous gRPC transport for OTel OTLP logs export.
 * Requires the php-grpc extension.
 */
class GrpcLogsTransport implements TransportInterface
{
    private LogsServiceClient $client;

    public function __construct(string $endpoint)
    {
        $this->client = new LogsServiceClient(
            $endpoint,
            ['credentials' => \Grpc\ChannelCredentials::createInsecure()]
        );
    }

    public function contentType(): string
    {
        return 'application/grpc';
    }

    public function send(string $payload, ?CancellationInterface $cancellation = null): FutureInterface
    {
        $request = new ExportLogsServiceRequest();
        $request->mergeFromString($payload);
        /** @var array{0: mixed, 1: \stdClass} $result */
        $result = $this->client->Export($request)->wait();
        $status = $result[1];
        if ($status->code !== \Grpc\STATUS_OK) {
            return new ErrorFuture(new \RuntimeException('gRPC export failed: ' . $status->details));
        }
        return new CompletedFuture('');
    }

    public function shutdown(?CancellationInterface $cancellation = null): bool
    {
        $this->client->close();
        return true;
    }

    public function forceFlush(?CancellationInterface $cancellation = null): bool
    {
        return true;
    }
}

class GrpcLogsTransportFactory implements TransportFactoryInterface
{
    public function create(
        string $endpoint,
        string $contentType,
        array $headers = [],
        $compression = null,
        float $timeout = 10.,
        int $retryDelay = 100,
        int $maxRetries = 3,
        ?string $cacert = null,
        ?string $cert = null,
        ?string $key = null,
    ): TransportInterface {
        // Strip trailing path from endpoint for gRPC (gRPC uses host:port only)
        $parsed = parse_url($endpoint);
        $host = $parsed['host'] ?? 'localhost';
        $port = $parsed['port'] ?? 4317;
        return new GrpcLogsTransport("$host:$port");
    }
}
