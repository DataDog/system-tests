<?php

/**
 * Data Streams Monitoring endpoints (tests/integrations/test_dsm.py).
 *
 * GET /dsm?integration=kafka|rabbitmq|rabbitmq_topic_exchange|rabbitmq_fanout_exchange
 *     Produces and then consumes through the integration, and answers "ok" once every message it
 *     waits for has been consumed.
 * GET /dsm/inject?topic=&integration=
 *     Sets an outbound checkpoint and answers with the carrier holding its pathway context.
 * GET /dsm/extract?topic=&integration=&ctx=
 *     Sets an inbound checkpoint for the pathway context in the JSON carrier ctx.
 *
 * PHP has no public manual checkpoint API, so /dsm/manual/* is not implemented.
 */

require_once __DIR__ . '/vendor/autoload.php';

use PhpAmqpLib\Connection\AMQPStreamConnection;
use PhpAmqpLib\Exception\AMQPTimeoutException;
use PhpAmqpLib\Message\AMQPMessage;

const DSM_KAFKA_SERVER = 'kafka:9092';
const DSM_RABBITMQ_HOST = 'rabbitmq';
const DSM_RABBITMQ_PORT = 5672;

function dsm_kafka_produce($topic, $message)
{
    $conf = new RdKafka\Conf();
    $conf->set('bootstrap.servers', DSM_KAFKA_SERVER);
    $producer = new RdKafka\Producer($conf);
    $producer->newTopic($topic)->produce(RD_KAFKA_PARTITION_UA, 0, $message);
    $err = $producer->flush(10000);
    if ($err !== RD_KAFKA_RESP_ERR_NO_ERROR) {
        throw new RuntimeException('Kafka produce failed: ' . rd_kafka_err2str($err));
    }
}

/**
 * Consume from partition 0 of the topic from the group's committed offset until the message comes
 * back, committing as it goes so that the next request starts after it.
 *
 * The partition is assigned rather than subscribed to: Test_DsmKafka waits only the weblog's
 * default request timeout, too short for a group rebalance to be sure to finish. The consumer
 * still belongs to the group, so its checkpoints carry the group tag.
 */
function dsm_kafka_consume($topic, $group, $message, $timeout)
{
    $conf = new RdKafka\Conf();
    $conf->set('bootstrap.servers', DSM_KAFKA_SERVER);
    $conf->set('group.id', $group);
    $conf->set('auto.offset.reset', 'earliest');
    $conf->set('enable.auto.commit', 'false');
    $consumer = new RdKafka\KafkaConsumer($conf);
    $consumer->assign([new RdKafka\TopicPartition($topic, 0, RD_KAFKA_OFFSET_STORED)]);

    try {
        $deadline = microtime(true) + $timeout;
        while (microtime(true) < $deadline) {
            $received = $consumer->consume(1000);
            if ($received->err === RD_KAFKA_RESP_ERR_NO_ERROR) {
                $consumer->commit($received);
                if ($received->payload === $message) {
                    return true;
                }
            } elseif ($received->err !== RD_KAFKA_RESP_ERR__TIMED_OUT
                    && $received->err !== RD_KAFKA_RESP_ERR__PARTITION_EOF) {
                throw new RuntimeException('Kafka consume failed: ' . $received->errstr());
            }
        }
        return false;
    } finally {
        $consumer->close();
    }
}

function dsm_kafka($queue, $group, $timeout)
{
    $message = 'Hello from PHP DSM test ' . uniqid();
    dsm_kafka_produce($queue, $message);
    if (!dsm_kafka_consume($queue, $group, $message, $timeout)) {
        throw new RuntimeException("Kafka message not consumed from $queue within {$timeout}s");
    }
}

/**
 * Declare the exchange and its queues, publish a message for each routing key, then consume until
 * every queue has delivered one.
 *
 * @param array $bindings queue => binding key
 */
function dsm_rabbitmq($exchange, $type, array $bindings, array $routingKeys, $timeout)
{
    $connection = new AMQPStreamConnection(DSM_RABBITMQ_HOST, DSM_RABBITMQ_PORT, 'guest', 'guest');
    try {
        $channel = $connection->channel();
        // Durable, as in the other tracers' weblogs, so that queues they left in a reused broker
        // can be declared again.
        $channel->exchange_declare($exchange, $type, false, true, false);
        foreach ($bindings as $queue => $bindingKey) {
            $channel->queue_declare($queue, false, true, false, false);
            $channel->queue_bind($queue, $exchange, $bindingKey);
        }

        foreach ($routingKeys as $routingKey) {
            $channel->basic_publish(new AMQPMessage('Hello from PHP DSM test'), $exchange, $routingKey);
        }

        $pending = array_fill_keys(array_keys($bindings), true);
        foreach (array_keys($bindings) as $queue) {
            $channel->basic_consume($queue, '', false, true, false, false, function () use ($queue, &$pending) {
                unset($pending[$queue]);
            });
        }
        $deadline = microtime(true) + $timeout;
        while ($pending && ($remaining = $deadline - microtime(true)) > 0) {
            try {
                $channel->wait(null, false, $remaining);
            } catch (AMQPTimeoutException $e) {
                break;
            }
        }
        $channel->close();
    } finally {
        $connection->close();
    }

    if ($pending) {
        throw new RuntimeException('RabbitMQ messages not consumed from ' . implode(', ', array_keys($pending))
            . " within {$timeout}s");
    }
}

function dsm()
{
    $integration = isset($_GET['integration']) ? $_GET['integration'] : '';
    $timeout = isset($_GET['timeout']) ? (float)$_GET['timeout'] : 20;

    switch ($integration) {
        case 'kafka':
            dsm_kafka($_GET['queue'], $_GET['group'], $timeout);
            break;
        case 'rabbitmq':
            dsm_rabbitmq(
                $_GET['exchange'],
                'direct',
                [$_GET['queue'] => $_GET['routing_key']],
                [$_GET['routing_key']],
                $timeout
            );
            break;
        case 'rabbitmq_topic_exchange':
            dsm_rabbitmq(
                'systemTestTopicExchange',
                'topic',
                [
                    'systemTestRabbitmqTopicQueue1' => 'test.topic.*.cake',
                    'systemTestRabbitmqTopicQueue2' => 'test.topic.vanilla.*',
                    'systemTestRabbitmqTopicQueue3' => 'test.topic.chocolate.*',
                ],
                ['test.topic.chocolate.cake', 'test.topic.chocolate.icecream', 'test.topic.vanilla.icecream'],
                $timeout
            );
            break;
        case 'rabbitmq_fanout_exchange':
            dsm_rabbitmq(
                'systemTestFanoutExchange',
                'fanout',
                [
                    'systemTestRabbitmqFanoutQueue1' => '',
                    'systemTestRabbitmqFanoutQueue2' => '',
                    'systemTestRabbitmqFanoutQueue3' => '',
                ],
                [''],
                $timeout
            );
            break;
        default:
            http_response_code(400);
            echo "Integration is not supported: $integration";
            return;
    }

    echo 'ok';
}

function dsm_require_checkpoints()
{
    if (!function_exists('DDTrace\Internal\dsm_set_checkpoint')) {
        throw new RuntimeException('This tracer has no Data Streams Monitoring checkpoints');
    }
}

function dsm_inject()
{
    dsm_require_checkpoints();
    $context = \DDTrace\Internal\dsm_set_checkpoint([
        'direction:out',
        'topic:' . $_GET['topic'],
        'type:' . $_GET['integration'],
    ]);

    $carrier = [];
    if ($context !== null) {
        $carrier['dd-pathway-ctx-base64'] = $context;
    }
    header('Content-Type: application/json');
    echo json_encode($carrier);
}

function dsm_extract()
{
    dsm_require_checkpoints();
    $carrier = json_decode($_GET['ctx'], true);
    \DDTrace\Internal\dsm_set_checkpoint(
        ['direction:in', 'topic:' . $_GET['topic'], 'type:' . $_GET['integration']],
        isset($carrier['dd-pathway-ctx-base64']) ? $carrier['dd-pathway-ctx-base64'] : null
    );
    echo 'ok';
}

$path = isset($_SERVER['PATH_INFO']) ? rtrim($_SERVER['PATH_INFO'], '/') : '';
try {
    switch ($path) {
        case '':
            dsm();
            break;
        case '/inject':
            dsm_inject();
            break;
        case '/extract':
            dsm_extract();
            break;
        default:
            http_response_code(404);
            echo "Not found: /dsm$path";
    }
} catch (Throwable $e) {
    error_log("DSM endpoint /dsm$path failed: $e");
    http_response_code(500);
    echo $e->getMessage();
}
