package com.datadoghq.system_tests.springboot;

import com.datadoghq.system_tests.springboot.aws.KinesisConnector;
import com.datadoghq.system_tests.springboot.aws.SnsConnector;
import com.datadoghq.system_tests.springboot.aws.SqsConnector;
import com.datadoghq.system_tests.springboot.Carrier;
import com.datadoghq.system_tests.springboot.data_streams.DSMContextCarrier;
import com.datadoghq.system_tests.springboot.grpc.WebLogInterface;
import com.datadoghq.system_tests.springboot.grpc.SynchronousWebLogGrpc;
import com.datadoghq.system_tests.springboot.kafka.KafkaConnector;
import com.datadoghq.system_tests.springboot.rabbitmq.RabbitmqConnector;
import com.datadoghq.system_tests.springboot.rabbitmq.RabbitmqConnectorForDirectExchange;
import com.datadoghq.system_tests.springboot.rabbitmq.RabbitmqConnectorForFanoutExchange;
import com.datadoghq.system_tests.springboot.rabbitmq.RabbitmqConnectorForTopicExchange;
import com.datadoghq.system_tests.iast.utils.Utils;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText;
import com.mongodb.MongoClient;
import com.mongodb.client.MongoCollection;
import datadog.appsec.api.blocking.Blocking;
import datadog.trace.api.EventTracker;
import datadog.trace.api.Trace;
import datadog.trace.api.experimental.*;
import datadog.trace.api.interceptor.MutableSpan;


import java.nio.charset.StandardCharsets;
import org.springframework.boot.autoconfigure.r2dbc.R2dbcAutoConfiguration;
import org.springframework.web.server.ResponseStatusException;


import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.api.trace.SpanBuilder;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.propagation.TextMapSetter;
import io.opentelemetry.context.Scope;
import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;
import ognl.Ognl;
import ognl.OgnlException;
import org.bson.Document;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.event.EventListener;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.File;
import java.io.FileNotFoundException;
import java.time.Instant;
import java.util.Collections;
import java.util.Scanner;
import java.util.LinkedHashMap;

import org.springframework.web.servlet.view.RedirectView;

import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;
import java.util.HashMap;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;
import java.nio.file.Files;
import java.nio.file.Paths;

import io.opentracing.Span;
import io.opentracing.util.GlobalTracer;

import static com.mongodb.client.model.Filters.eq;
import static io.opentelemetry.api.trace.SpanKind.INTERNAL;
import static io.opentelemetry.api.trace.StatusCode.ERROR;
import static java.time.temporal.ChronoUnit.SECONDS;


@RestController
@EnableAutoConfiguration(exclude = R2dbcAutoConfiguration.class)
@ComponentScan(basePackages = {"com.datadoghq.system_tests.springboot"})
public class App {

    CassandraConnector cassandra;
    MongoClient mongoClient;
    int PRODUCE_CONSUME_THREAD_TIMEOUT = 5000;

    @RequestMapping("/")
    String home(HttpServletResponse response) {
        // open liberty set this header to en-US by default, it breaks the APPSEC-BLOCKING scenario
        // if a java engineer knows how to remove this?
        // waiting for that, just set a random value
        response.setHeader("Content-Language", "not-set");
        return "Hello World!";
    }

    @RequestMapping("/healthcheck")
    Map<String, Object> healtchcheck() {

        String filePath = "/app/SYSTEM_TESTS_LIBRARY_VERSION";
        String version;
        try {
            version = new String(Files.readAllBytes(Paths.get(filePath)));
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Can't get version");
        }

        Map<String, String> library = new HashMap<>();
        library.put("name", "java_otel");
        library.put("version", version.strip());

        Map<String, Object> response = new HashMap<>();
        response.put("status", "ok");
        response.put("library", library);

        return response;
    }

    @GetMapping("/headers")
    String headers(HttpServletResponse response) {
        response.setHeader("content-language", "en-US");
        return "012345678901234567890123456789012345678901";
    }

    @RequestMapping(value = "/tag_value/{value}/{code}", method = {RequestMethod.GET, RequestMethod.OPTIONS}, headers = "accept=*")
    ResponseEntity<String> tagValue(@PathVariable final String value, @PathVariable final int code) {
        setRootSpanTag("appsec.events.system_tests_appsec_event.value", value);
        return ResponseEntity.status(code).body("Value tagged");
    }

    @PostMapping(value = "/tag_value/{value}/{code}", headers = "accept=*",
            consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    ResponseEntity<String> tagValueWithUrlencodedBody(@PathVariable final String value, @PathVariable final int code, @RequestParam MultiValueMap<String, String> body) {
        return tagValue(value, code);
    }

    @RequestMapping("/waf/**")
    String waf() {
        return "Hello World!";
    }

    @RequestMapping("/waf/{param}")
    String wafWithParams(@PathVariable("param") String param) {
        return "Hello World!";
    }

    @PostMapping(value = "/waf",
            consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    String postWafUrlencoded(@RequestParam MultiValueMap<String, String> body) {
        return body.toString();
    }

    @PostMapping(value = "/waf",
            consumes = MediaType.APPLICATION_JSON_VALUE)
    String postWafJson(@RequestBody Object body) {
        return body.toString();
    }

    @PostMapping(value = "/waf", consumes = MediaType.APPLICATION_XML_VALUE)
    String postWafXml(@RequestBody XmlObject object) {
        return object.toString();
    }

    @GetMapping(value = "/session/new")
    ResponseEntity<String> newSession(final HttpServletRequest request) {
        final HttpSession session = request.getSession(true);
        return ResponseEntity.ok(session.getId());
    }

    @GetMapping(value = "/session/user")
    ResponseEntity<String> userSession(@RequestParam("sdk_user") final String sdkUser, final HttpServletRequest request) {
        EventTracker tracker = datadog.trace.api.GlobalTracer.getEventTracker();
        tracker.trackLoginSuccessEvent(sdkUser, Collections.emptyMap());
        return ResponseEntity.ok(request.getRequestedSessionId());
    }

    @RequestMapping("/status")
    ResponseEntity<String> status(@RequestParam Integer code) {
        return new ResponseEntity<>(HttpStatus.valueOf(code));
    }

    private static final Map<String, String> METADATA = createMetadata();
    private static final Map<String, String> createMetadata() {
        HashMap<String, String> h = new HashMap<>();
        h.put("metadata0", "value0");
        h.put("metadata1", "value1");
        return h;
    }

    @GetMapping("/users")
    String users(@RequestParam String user) {
        final Span span = GlobalTracer.get().activeSpan();
        if ((span instanceof MutableSpan)) {
            MutableSpan localRootSpan = ((MutableSpan) span).getLocalRootSpan();
            localRootSpan.setTag("usr.id", user);
        }
        Blocking
                .forUser(user)
                .blockIfMatch();
        return "Hello " + user;
    }

    @GetMapping("/user_login_success_event")
    public String userLoginSuccess(
            @RequestParam(value = "event_user_id", defaultValue = "system_tests_user") String userId) {
        datadog.trace.api.GlobalTracer.getEventTracker()
                .trackLoginSuccessEvent(userId, METADATA);

        return "ok";
    }

    @GetMapping("/user_login_failure_event")
    public String userLoginFailure(
            @RequestParam(value = "event_user_id", defaultValue = "system_tests_user") String userId,
            @RequestParam(value = "event_user_exists", defaultValue = "true") boolean eventUserExists) {
        datadog.trace.api.GlobalTracer.getEventTracker()
                .trackLoginFailureEvent(userId, eventUserExists, METADATA);

        return "ok";
    }

    @GetMapping("/custom_event")
    public String customEvent(
            @RequestParam(value = "event_name", defaultValue = "system_tests_event") String eventName) {
        datadog.trace.api.GlobalTracer.getEventTracker()
                .trackCustomEvent(eventName, METADATA);

        return "ok";
    }

    @JacksonXmlRootElement
    public static class XmlObject {
        public XmlObject() {}
        public XmlObject(String value) { this.value = value; }

        @JacksonXmlText
        public String value;

        @JacksonXmlProperty
        public String attack;

        @Override
        public String toString() {
            final StringBuilder sb = new StringBuilder("AElement{");
            sb.append("value='").append(value).append('\'');
            sb.append(", attack='").append(attack).append('\'');
            sb.append('}');
            return sb.toString();
        }
    }

    @RequestMapping("/sample_rate_route/{i}")
    String sample_route(@PathVariable("i") String i) {
        return "OK";
    }

    @RequestMapping("/params/{str}")
    String params_route(@PathVariable("str") String str) {
        return "OK";
    }

    @RequestMapping("/trace/sql")
    String traceSQL() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        // NOTE: see README.md for setting up the docker image to quickly test this

        String url = "jdbc:postgresql://postgres_db/sportsdb?user=postgres&password=postgres";
        try (Connection pgConn = DriverManager.getConnection(url)) {

            Statement st = pgConn.createStatement();
            ResultSet rs = st.executeQuery("SELECT * FROM display_names LIMIT 10");
            while (rs.next())
            {
                System.out.print("Column 2 returned ");
                System.out.println(rs.getString(2));
            }
            rs.close();
            st.close();
        } catch (SQLException e) {
            e.printStackTrace(System.err);
            return "pgsql exception :(";
        }

        return "hi SQL";
    }

    @RequestMapping("/trace/http")
    String traceHTTP() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        try {
            URL server = new URL("http://example.com");
            HttpURLConnection connection = (HttpURLConnection)server.openConnection();
            connection.connect();
            System.out.println("Response code:" + connection.getResponseCode());
        } catch (Exception e) {
            e.printStackTrace(System.err);
            return "ssrf exception :(";
        }
        return "hi HTTP";
    }

    @RequestMapping("/trace/cassandra")
    String traceCassandra() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        cassandra.getSession().execute("SELECT * FROM \"table\" WHERE id = 1").all();

        return "hi Cassandra";
    }

    @RequestMapping("/trace/mongo")
    String traceMongo() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        MongoCollection<Document> collection = mongoClient.getDatabase("mydb").getCollection("test");
        Document doc = collection.find(eq("id", 3)).first();
        if (doc != null) {
            return "hi Mongo, " + doc.get("subject").toString();
        }
        return "hi Mongo";
    }

    @RequestMapping("/kafka/produce")
    ResponseEntity<String> kafkaProduce(@RequestParam(required = true) String topic) {
        KafkaConnector kafka = new KafkaConnector(topic);
        try {
            kafka.produceMessageWithoutNewThread("DistributedTracing from Java");
        } catch (Exception e) {
            System.out.println("[kafka] Failed to start producing message...");
            e.printStackTrace();
            return new ResponseEntity<>("failed to start producing messages", HttpStatus.BAD_REQUEST);
        }
        return new ResponseEntity<>("produce ok", HttpStatus.OK);
    }

    @RequestMapping("/kafka/consume")
    ResponseEntity<String> kafkaConsume(@RequestParam(required = true) String topic, @RequestParam(required = false) Integer timeout) {
        KafkaConnector kafka = new KafkaConnector(topic);
        if (timeout == null) {
            timeout = Integer.MAX_VALUE;
        } else {
            // convert from seconds to ms
            timeout *= 1000;
        }
        boolean consumed = false;
        try {
            consumed = kafka.consumeMessageWithoutNewThread(timeout);
            return consumed ? new ResponseEntity<>("consume ok", HttpStatus.OK) : new ResponseEntity<>("consume timed out", HttpStatus.BAD_REQUEST);
        } catch (Exception e) {
            System.out.println("[kafka] Failed to start consuming message...");
            e.printStackTrace();
            return new ResponseEntity<>("failed to start consuming messages", HttpStatus.BAD_REQUEST);
        }
    }

    @RequestMapping("/sqs/produce")
    ResponseEntity<String> sqsProduce(
        @RequestParam(required = true) String queue,
        @RequestParam(required = true) String message
    ) {
        SqsConnector sqs = new SqsConnector(queue);
        try {
            sqs.produceMessageWithoutNewThread(message);
        } catch (Exception e) {
            System.out.println("[SQS] Failed to start producing message...");
            e.printStackTrace();
            return new ResponseEntity<>("failed to start producing messages", HttpStatus.BAD_REQUEST);
        }
        return new ResponseEntity<>("produce ok", HttpStatus.OK);
    }

    @RequestMapping("/sqs/consume")
    ResponseEntity<String> sqsConsume(
        @RequestParam(required = true) String queue,
        @RequestParam(required = false) Integer timeout,
        @RequestParam(required = true) String message
    ) {
        SqsConnector sqs = new SqsConnector(queue);
        if (timeout == null) timeout = 60;
        boolean consumed = false;
        try {
            consumed = sqs.consumeMessageWithoutNewThread("SQS", message);
            return consumed ? new ResponseEntity<>("consume ok", HttpStatus.OK) : new ResponseEntity<>("consume timed out", HttpStatus.BAD_REQUEST);
        } catch (Exception e) {
            System.out.println("[SQS] Failed to start consuming message...");
            e.printStackTrace();
            return new ResponseEntity<>("failed to start consuming messages", HttpStatus.BAD_REQUEST);
        }
    }

    @RequestMapping("/sns/produce")
    ResponseEntity<String> snsProduce(
        @RequestParam(required = true) String queue,
        @RequestParam(required = true) String topic,
        @RequestParam(required = true) String message
    ) {
        SnsConnector sns = new SnsConnector(topic);
        SqsConnector sqs = new SqsConnector(queue);
        try {
            sns.produceMessageWithoutNewThread(message, sqs);
        } catch (Exception e) {
            System.out.println("[SNS->SQS] Failed to start producing message...");
            e.printStackTrace();
            return new ResponseEntity<>("[SNS->SQS] failed to start producing messages", HttpStatus.BAD_REQUEST);
        }
        return new ResponseEntity<>("produce ok", HttpStatus.OK);
    }

    @RequestMapping("/sns/consume")
    ResponseEntity<String> snsConsume(
        @RequestParam(required = true) String queue,
        @RequestParam(required = false) Integer timeout,
        @RequestParam(required = true) String message
    ) {
        SqsConnector sqs = new SqsConnector(queue);
        if (timeout == null) timeout = 60;
        boolean consumed = false;
        try {
            consumed = sqs.consumeMessageWithoutNewThread("SNS->SQS", message);
            return consumed ? new ResponseEntity<>("consume ok", HttpStatus.OK) : new ResponseEntity<>("consume timed out", HttpStatus.BAD_REQUEST);
        } catch (Exception e) {
            System.out.println("[SNS->SQS] Failed to start consuming message...");
            e.printStackTrace();
            return new ResponseEntity<>("[SNS->SQS] failed to start consuming messages", HttpStatus.BAD_REQUEST);
        }
    }

    @RequestMapping("/kinesis/produce")
    ResponseEntity<String> kinesisProduce(
        @RequestParam(required = true) String stream,
        @RequestParam(required = true) String message
    ) {
        KinesisConnector kinesis = new KinesisConnector(stream);
        try {
            kinesis.produceMessageWithoutNewThread(message);
        } catch (Exception e) {
            System.out.println("[Kinesis] Failed to start producing message...");
            e.printStackTrace();
            return new ResponseEntity<>("[Kinesis] failed to start producing messages", HttpStatus.BAD_REQUEST);
        }
        return new ResponseEntity<>("produce ok", HttpStatus.OK);
    }

    @RequestMapping("/kinesis/consume")
    ResponseEntity<String> kinesisConsume(
        @RequestParam(required = true) String stream,
        @RequestParam(required = false) Integer timeout,
        @RequestParam(required = true) String message
    ) {
        KinesisConnector kinesis = new KinesisConnector(stream);
        if (timeout == null) timeout = 60;
        boolean consumed = false;
        try {
            consumed = kinesis.consumeMessageWithoutNewThread(timeout, message);
            return consumed ? new ResponseEntity<>("consume ok", HttpStatus.OK) : new ResponseEntity<>("consume timed out", HttpStatus.BAD_REQUEST);
        } catch (Exception e) {
            System.out.println("[Kinesis] Failed to start consuming message...");
            e.printStackTrace();
            return new ResponseEntity<>("[Kinesis] failed to start consuming messages", HttpStatus.BAD_REQUEST);
        }
    }

    @RequestMapping("/rabbitmq/produce")
    ResponseEntity<String> rabbitmqProduce(@RequestParam(required = true) String queue, @RequestParam(required = true) String exchange) {
        RabbitmqConnector rabbitmq = new RabbitmqConnector();
        try {
            Thread produceThread = rabbitmq.startProducingMessageWithQueue("RabbitMQ Context Propagation Test from Java", queue, exchange);
            produceThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
        } catch (Exception e) {
            System.out.println("[RabbitMQ] Failed to start producing message...");
            e.printStackTrace();
            return new ResponseEntity<>("failed to start producing messages", HttpStatus.BAD_REQUEST);
        }
        return new ResponseEntity<>("produce ok", HttpStatus.OK);
    }

    @RequestMapping("/rabbitmq/consume")
    ResponseEntity<String> rabbitmqConsume(
        @RequestParam(required = true) String queue,
        @RequestParam(required = true) String exchange,
        @RequestParam(required = false) Integer timeout
    ) {
        RabbitmqConnector rabbitmq = new RabbitmqConnector();
        if (timeout == null) timeout = 60;
        boolean consumed = false;
        try {
            consumed = rabbitmq.startConsumingMessagesWithQueue(queue, exchange, timeout).get();
            return consumed ? new ResponseEntity<>("consume ok", HttpStatus.OK) : new ResponseEntity<>("consume timed out", HttpStatus.BAD_REQUEST);
        } catch (Exception e) {
            System.out.println("[RabbitMQ] Failed to start consuming message...");
            e.printStackTrace();
            return new ResponseEntity<>("failed to start consuming messages", HttpStatus.BAD_REQUEST);
        }
    }

    @RequestMapping("/dsm")
    String publishToKafka(
        @RequestParam(required = true, name = "integration") String integration,
        @RequestParam(required = false, name = "topic") String topic,
        @RequestParam(required = false, name = "queue") String queue,
        @RequestParam(required = false, name = "stream") String stream,
        @RequestParam(required = false, name = "routing_key") String routing_key,
        @RequestParam(required = false, name = "exchange") String exchange,
        @RequestParam(required = false, name = "group") String group,
        @RequestParam(required = false, name = "message") String message
    ) {
        if ("kafka".equals(integration)) {
            KafkaConnector kafka = new KafkaConnector(queue);
            try {
                Thread produceThread = kafka.startProducingMessage("hello world!");
                produceThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[kafka] Failed to start producing message...");
                e.printStackTrace();
                return "failed to start producing message";
            }
            try {
                Thread consumeThread = kafka.startConsumingMessages("");
                consumeThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[kafka] Failed to start consuming message...");
                e.printStackTrace();
                return "failed to start consuming message";
            }
        } else if ("rabbitmq".equals(integration)) {
            RabbitmqConnectorForDirectExchange rabbitmq = new RabbitmqConnectorForDirectExchange(queue, exchange, routing_key);
            try {
                Thread produceThread = rabbitmq.startProducingMessages();
                produceThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[rabbitmq] Failed to start producing message...");
                e.printStackTrace();
                return "failed to start producing message";
            }
            try {
                Thread consumeThread = rabbitmq.startConsumingMessages();
                consumeThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[rabbitmq] Failed to start consuming message...");
                e.printStackTrace();
                return "failed to start consuming message";
            }
        } else if ("rabbitmq_topic_exchange".equals(integration)) {
            RabbitmqConnectorForTopicExchange rabbitmq = new RabbitmqConnectorForTopicExchange();
            try {
                Thread produceThread = rabbitmq.startProducingMessages();
                produceThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[rabbitmq_topic] Failed to start producing message...");
                e.printStackTrace();
                return "failed to start producing message";
            }
            try {
                Thread consumeThread = rabbitmq.startConsumingMessages();
                consumeThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[rabbitmq_topic] Failed to start consuming message...");
                e.printStackTrace();
                return "failed to start consuming message";
            }
        } else if ("rabbitmq_fanout_exchange".equals(integration)) {
            RabbitmqConnectorForFanoutExchange rabbitmq = new RabbitmqConnectorForFanoutExchange();
            try {
                Thread produceThread = rabbitmq.startProducingMessages();
                produceThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[rabbitmq_fanout] Failed to start producing message...");
                e.printStackTrace();
                return "failed to start producing message";
            }
            try {
                Thread consumeThread = rabbitmq.startConsumingMessages();
                consumeThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[rabbitmq_fanout] Failed to start consuming message...");
                e.printStackTrace();
                return "failed to start consuming message";
            }
        } else if ("sqs".equals(integration)) {
            SqsConnector sqs = new SqsConnector(queue);
            try {
                Thread produceThread = sqs.startProducingMessage(message);
                produceThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[SQS] Failed to start producing message...");
                e.printStackTrace();
                return "[SQS] failed to start producing message";
            }
            try {
                Thread consumeThread = sqs.startConsumingMessages("SQS", message);
                consumeThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[SQS] Failed to start consuming message...");
                e.printStackTrace();
                return "[SQS] failed to start consuming message";
            }
        } else if ("sns".equals(integration)) {
            SnsConnector sns = new SnsConnector(topic);
            SqsConnector sqs = new SqsConnector(queue);
            try {
                Thread produceThread = sns.startProducingMessage(message, sqs);
                produceThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[SNS->SQS] Failed to start producing message...");
                e.printStackTrace();
                return "[SNS->SQS] failed to start producing message";
            }
            try {
                Thread consumeThread = sqs.startConsumingMessages("SNS->SQS", message);
                consumeThread.join(this.PRODUCE_CONSUME_THREAD_TIMEOUT);
            } catch (Exception e) {
                System.out.println("[SNS->SQS] Failed to start consuming message...");
                e.printStackTrace();
                return "[SNS->SQS] failed to start consuming message";
            }
        } else if ("kinesis".equals(integration)) {
            KinesisConnector kinesis = new KinesisConnector(stream);
            try {
                kinesis.produceMessageWithoutNewThread(message);
            } catch (Exception e) {
                System.out.println("[Kinesis] Failed to start producing message...");
                e.printStackTrace();
                return "[Kinesis] failed to start producing message";
            }
            try {
                kinesis.consumeMessageWithoutNewThread(60, message);
            } catch (Exception e) {
                System.out.println("[Kinesis] Failed to start consuming message...");
                e.printStackTrace();
                return "[Kinesis] failed to start consuming message";
            }
        } else {
            return "unknown integration: " + integration;
        }
        return "ok";
    }

    @RequestMapping("/dsm/inject")
    String dsmInject(
        @RequestParam(required = true, name = "integration") String integration,
        @RequestParam(required = true, name = "topic") String topic
    ) throws com.fasterxml.jackson.core.JsonProcessingException {
        Span span = GlobalTracer.get().buildSpan("kafka.produce").ignoreActiveSpan().start();
        GlobalTracer.get().activateSpan(span);

        Map<String, Object> headers = new HashMap<String, Object>();
        Carrier headersAdapter = new Carrier(headers);

        DataStreamsCheckpointer.get().setProduceCheckpoint(integration, topic, headersAdapter);

        // Convert headers map to JSON string
        ObjectMapper mapper = new ObjectMapper();
        String jsonString = mapper.writeValueAsString(headers);

        span.finish();

        return jsonString;
    }

    @RequestMapping("/dsm/extract")
    String dsmExtract(
        @RequestParam(required = true, name = "integration") String integration,
        @RequestParam(required = true, name = "topic") String topic,
        @RequestParam(required = true, name = "ctx") String ctx
    ) throws com.fasterxml.jackson.core.JsonProcessingException {
        Span span = GlobalTracer.get().buildSpan("kafka.consume").ignoreActiveSpan().start();
        GlobalTracer.get().activateSpan(span);

        ObjectMapper mapper = new ObjectMapper();
        Map<String, Object> headers = mapper.readValue(ctx, new TypeReference<Map<String, Object>>(){});
        Carrier headersAdapter = new Carrier(headers);

        DataStreamsCheckpointer.get().setConsumeCheckpoint(integration, topic, headersAdapter);

        span.finish();

        return "ok";
    }

    @RequestMapping("/dsm/manual/produce")
    String dsmManualCheckpointProduce(
        @RequestParam(required = true, name = "type") String type,
        @RequestParam(required = true, name = "target") String target,
        HttpServletResponse response
    ) {
        DSMContextCarrier headers = new DSMContextCarrier();

        DataStreamsCheckpointer dsmCheckpointer = DataStreamsCheckpointer.get();

        dsmCheckpointer.setProduceCheckpoint(type, target, headers);

        System.out.println("[DSM Manual Produce] After completion: " + headers.getData());

        // Add headers that include DSM pathway context to response headers
        for (Map.Entry<String, Object> entry : headers.entries()) {
            response.addHeader(entry.getKey(), entry.getValue().toString());
        }
        return "ok";
    }

    @RequestMapping("/dsm/manual/produce_with_thread")
    String dsmManualCheckpointProduceWithThread(
        @RequestParam(required = true, name = "type") String type,
        @RequestParam(required = true, name = "target") String target,
        HttpServletResponse response
    ) throws java.lang.InterruptedException, java.util.concurrent.ExecutionException {
        class DsmProduce implements Callable<Map<String, Object>> {
            @Override
            public Map<String, Object> call() {
                DSMContextCarrier headers = new DSMContextCarrier();
                DataStreamsCheckpointer dsmCheckpointer = DataStreamsCheckpointer.get();

                System.out.println("[DSM Manual Produce with Thread] Before setProduceCheckpoint: " + headers.getData());

                dsmCheckpointer.setProduceCheckpoint(type, target, headers);

                System.out.println("[DSM Manual Produce with Thread] After setProduceCheckpoint: " + headers.getData());

                return headers.getData();
            }
        }

        ExecutorService executor = Executors.newFixedThreadPool(1);
        Future<Map<String, Object>> dsmProduceFuture = executor.submit(new DsmProduce());
        Map<String, Object> injectedHeaders = dsmProduceFuture.get();

        System.out.println("[DSM Manual Produce with Thread] After thread completion: " + injectedHeaders);

        // Add headers that include DSM pathway context to response headers
        for (Map.Entry<String, Object> entry : injectedHeaders.entrySet()) {
            response.addHeader(entry.getKey(), entry.getValue().toString());
        }

        return "ok";
    }

    @RequestMapping("/dsm/manual/consume")
    String dsmManualCheckpointConsume(
        @RequestParam(required = true, name = "type") String type,
        @RequestParam(required = true, name = "source") String source,
        @RequestHeader(name = "_datadog", required = true) String datadogHeader
    ) throws com.fasterxml.jackson.core.JsonProcessingException {
        System.out.println("[DSM Manual Consume] consumed headers: " + datadogHeader);

        ObjectMapper mapper = new ObjectMapper();
        Map<String, Object> headersMap = mapper.readValue(datadogHeader, new TypeReference<Map<String, Object>>(){});
        DSMContextCarrier headersAdapter = new DSMContextCarrier(headersMap);

        DataStreamsCheckpointer.get().setConsumeCheckpoint(type, source, headersAdapter);

        return "ok";
    }

    @RequestMapping("/dsm/manual/consume_with_thread")
    String dsmManualCheckpointConsumeWithThread(
        @RequestParam(required = true, name = "type") String type,
        @RequestParam(required = true, name = "source") String source,
        @RequestHeader(name = "_datadog", required = true) String datadogHeader
    ) throws java.lang.InterruptedException, java.util.concurrent.ExecutionException {
        final String finalHeaders = datadogHeader;

        class DsmConsume implements Callable<String> {
            @Override
            public String call() throws com.fasterxml.jackson.core.JsonProcessingException {
                System.out.println("[DSM Manual Consume within Thread] consumed headers: " + finalHeaders);

                ObjectMapper mapper = new ObjectMapper();
                Map<String, Object> headersMap = mapper.readValue(finalHeaders, new TypeReference<Map<String, Object>>(){});
                DSMContextCarrier headersAdapter = new DSMContextCarrier(headersMap);

                DataStreamsCheckpointer dsmCheckpointer = DataStreamsCheckpointer.get();
                dsmCheckpointer.setConsumeCheckpoint(type, source, headersAdapter);

                return "ok";
            }
        }

        ExecutorService executor = Executors.newFixedThreadPool(1);
        Future<String> dsmConsumeFuture = executor.submit(new DsmConsume());
        String status = dsmConsumeFuture.get();

        return status;
    }

    @RequestMapping("/trace/ognl")
    String traceOGNL() {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        List<String> list = Arrays.asList("Have you ever thought about jumping off an airplane?",
                "Flying like a bird made of cloth who just left a perfectly working airplane");
        try {
            Object expr = Ognl.parseExpression("[1]");
            String value = (String) Ognl.getValue(expr, list);
            return "hi OGNL, " + value;
        } catch (OgnlException e) {
            e.printStackTrace();
        }

        return "hi OGNL";
    }

    @RequestMapping("/make_distant_call")
    DistantCallResponse make_distant_call(@RequestParam String url) throws Exception {
        URL urlObject = new URL(url);

        HttpURLConnection con = (HttpURLConnection) urlObject.openConnection();
        con.setRequestMethod("GET");

        // Save request headers
        HashMap<String, String> request_headers = new HashMap<String, String>();
        for (Map.Entry<String, List<String>> header: con.getRequestProperties().entrySet()) {
            if (header.getKey() == null) {
                continue;
            }

            request_headers.put(header.getKey(), header.getValue().get(0));
        }

        // Save response headers and status code
        int status_code = con.getResponseCode();
        HashMap<String, String> response_headers = new HashMap<String, String>();
        for (Map.Entry<String, List<String>> header: con.getHeaderFields().entrySet()) {
            if (header.getKey() == null) {
                continue;
            }

            response_headers.put(header.getKey(), header.getValue().get(0));
        }

        DistantCallResponse result = new DistantCallResponse();
        result.url = url;
        result.status_code = status_code;
        result.request_headers = request_headers;
        result.response_headers = response_headers;

        return result;
    }

    @RequestMapping("/createextraservice")
    public String createextraservice(@RequestParam String serviceName) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("service", serviceName);
        }
        return "OK";
    }

    public static final class DistantCallResponse {
        public String url;
        public int status_code;
        public HashMap<String, String> request_headers;
        public HashMap<String, String> response_headers;
    }

    @RequestMapping("/experimental/redirect")
    RedirectView traceRedirect(@RequestParam(required = false, name="url") String redirect) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span != null) {
            span.setTag("appsec.event", true);
        }

        if (redirect == null) {
            return new RedirectView("https://datadoghq.com");
        }
        return new RedirectView("https://" + redirect);
    }

    @RequestMapping("/e2e_otel_span")
    String e2eOtelSpan(@RequestHeader(name = "User-Agent") String userAgent,
                       @RequestParam(name="parentName") String parentName,
                       @RequestParam(name="childName") String childName,
                       @RequestParam(required = false, name="shouldIndex") int shouldIndex) {
        // Get an OpenTelemetry tracer
        Tracer tracer = GlobalOpenTelemetry.getTracer("system-tests");
        // Aggregate common attributes
        AttributesBuilder commonAttributesBuilder = Attributes.builder()
                .put("http.useragent", userAgent);
        if (shouldIndex == 1) {
            commonAttributesBuilder.put("_dd.filter.kept", 1);
            commonAttributesBuilder.put("_dd.filter.id", "system_tests_e2e");
        }
        Attributes commonAttributes = commonAttributesBuilder.build();
        // Create parent span according test requirements
        SpanBuilder parentSpanBuilder = tracer.spanBuilder(parentName)
                .setNoParent()
                .setAllAttributes(commonAttributes)
                .setAttribute("attributes", "values");
        io.opentelemetry.api.trace.Span parentSpan = parentSpanBuilder.startSpan();
        parentSpan.setStatus(ERROR, "testing_end_span_options");

        try (Scope scope = parentSpan.makeCurrent()) {
            // Create child span according test requirements
            Instant now = Instant.now();
            Instant oneSecLater = now.plus(1, SECONDS);

            io.opentelemetry.api.trace.Span childSpan = tracer.spanBuilder(childName)
                    .setStartTimestamp(now)
                    .setAllAttributes(commonAttributes)
                    .setSpanKind(INTERNAL)
                    .startSpan();

            childSpan.end(oneSecLater);
        }
        parentSpan.end();

        return "OK";
    }

    @RequestMapping("/e2e_single_span")
    String e2eSingleSpan(@RequestHeader(required = true, name = "User-Agent") String userAgent,
                         @RequestParam(required = true, name="parentName") String parentName,
                         @RequestParam(required = true, name="childName") String childName,
                         @RequestParam(required = false, name="shouldIndex") int shouldIndex) {
        // We want the parentSpan to be a true root-span (parentId==0).
        Span parentSpan = GlobalTracer.get().buildSpan(parentName).ignoreActiveSpan().withTag("http.useragent", userAgent).start();
        Span childSpan = GlobalTracer.get().buildSpan(childName).withTag("http.useragent", userAgent).asChildOf(parentSpan).start();

        if (shouldIndex == 1) {
            // Simulate a retention filter (see https://github.com/DataDog/system-tests/pull/898).
            parentSpan.setTag("_dd.filter.kept", 1);
            parentSpan.setTag("_dd.filter.id", "system_tests_e2e");
            childSpan.setTag("_dd.filter.kept", 1);
            childSpan.setTag("_dd.filter.id", "system_tests_e2e");
        }

        long nowMicros = System.currentTimeMillis() * 1000;
        long tenSecMicros = 10_000_000;
        childSpan.finish(nowMicros + tenSecMicros);
        parentSpan.finish(nowMicros + 2*tenSecMicros);

        return "OK";
    }

    @PostMapping(value = "/shell_execution", consumes = MediaType.APPLICATION_JSON_VALUE)
    ResponseEntity<String> shellExecution(@RequestBody final ShellExecutionRequest request) throws IOException, InterruptedException {
        Process p;
        if (request.options.shell) {
            throw new RuntimeException("Not implemented");
        } else {
            final String[] args = request.args.split("\\s+");
            final String[] command = new String[args.length + 1];
            command[0] = request.command;
            System.arraycopy(args, 0, command, 1, args.length);
            p = new ProcessBuilder(command).start();
        }
        p.waitFor(10, TimeUnit.SECONDS);
        final int exitCode = p.exitValue();
        return new ResponseEntity<>("OK: " + exitCode, HttpStatus.OK);
    }

    private static class ShellExecutionRequest {
        public String command;
        public String args;
        public Options options;

        static class Options {
            public boolean shell;
        }
    }

    @EventListener(ApplicationReadyEvent.class)
    @Trace
    public void init() {
        new AppReadyHandler(this).start();
    }

    @RequestMapping("/load_dependency")
    public String loadDep() throws ClassNotFoundException {
        Class<?> klass = this.getClass().getClassLoader().loadClass("org.apache.http.client.HttpClient");
        return "Loaded Dependency\n".concat(klass.toString());
    }

    @RequestMapping("/read_file")
    public ResponseEntity<String> readFile(@RequestParam String file) {
        String content;
        try {
            content = new Scanner(new File(file)).useDelimiter("\\Z").next();
        }
        catch (FileNotFoundException ex) {
            return new ResponseEntity<>(HttpStatus.BAD_REQUEST);
        }

        return new ResponseEntity<>(content, HttpStatus.OK);
    }

    @RequestMapping("/db")
    String db_sql_integrations(@RequestParam(required = true, name="service") String service,
                         @RequestParam(required = true, name="operation") String operation)
  {
        System.out.println("DB service [" + service + "], operation: [" + operation + "]");
        com.datadoghq.system_tests.springboot.integrations.db.DBFactory dbFactory = new com.datadoghq.system_tests.springboot.integrations.db.DBFactory();

        com.datadoghq.system_tests.springboot.integrations.db.ICRUDOperation crudOperation = dbFactory.getDBOperator(service);

        switch (operation) {
           case "init":
                crudOperation.createSampleData();
                break;
            case "select":
                crudOperation.select();
                break;
            case "select_error":
                crudOperation.selectError();
                break;
            case "insert":
                crudOperation.insert();
                break;
            case "delete":
                crudOperation.delete();
                break;
            case "update":
                crudOperation.update();
                break;
            case "procedure":
                crudOperation.callProcedure();
                break;
            default:
                throw new UnsupportedOperationException("Operation " + operation + " not allowed");
        }

        return "OK";
    }

    @GetMapping(value = "/requestdownstream")
    public String requestdownstream(HttpServletResponse response) throws IOException {
        String url = "http://localhost:7777/returnheaders";
        return Utils.sendGetRequest(url);
    }

    @GetMapping(value = "/returnheaders", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, String>> returnheaders(@RequestHeader Map<String, String> headers) {
        return ResponseEntity.ok(headers);
    }

    @GetMapping(value = "/set_cookie")
    public ResponseEntity<String> setCookie(@RequestParam String name, @RequestParam String value) {
        return ResponseEntity.ok().header("Set-Cookie", name + "=" + value).body("Cookie set");
    }


    @Bean
    @ConditionalOnProperty(
        value="spring.native",
        havingValue = "false",
        matchIfMissing = true)
    SynchronousWebLogGrpc synchronousGreeter(WebLogInterface localInterface) {
        return new SynchronousWebLogGrpc(localInterface.getPort());
   }

    @Bean
    @ConditionalOnProperty(
        value="spring.native",
        havingValue = "false",
        matchIfMissing = true)
    WebLogInterface localInterface() throws IOException {
        return new WebLogInterface();
    }

    private void setRootSpanTag(final String key, final String value) {
        final Span span = GlobalTracer.get().activeSpan();
        if (span instanceof MutableSpan) {
            final MutableSpan rootSpan = ((MutableSpan) span).getLocalRootSpan();
            if (rootSpan != null) {
                rootSpan.setTag(key, value);
            }
        }
    }

    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

}
