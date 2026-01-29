package com.datadoghq.trace.opentelemetry.controller;

import static com.datadoghq.ApmTestClient.LOGGER;

import com.datadoghq.trace.opentelemetry.dto.*;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.api.metrics.*;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(value = "/metrics/otel")
public class OpenTelemetryMetricsController {
  private final MeterProvider meterProvider = GlobalOpenTelemetry.getMeterProvider();

  /** Known meters, populated via getMeter requests. */
  private final Map<String, Meter> meters = new ConcurrentHashMap<>();

  /** Previously created instruments of various types. */
  private final Map<String, Object> instruments = new ConcurrentHashMap<>();

  @PostMapping("get_meter")
  public void getMeter(@RequestBody GetMeterArgs args) {
    LOGGER.info("Getting OTel meter: {}", args);
    String meterName = args.name();
    if (!meters.containsKey(meterName)) {
      meters.put(
          meterName,
          meterProvider
              .meterBuilder(meterName)
              .setInstrumentationVersion(args.version())
              .setSchemaUrl(args.schemaUrl())
              .build());
    }
  }

  @PostMapping("create_counter")
  public void createCounter(@RequestBody CreateCounterArgs args) {
    LOGGER.info("Creating OTel counter: {}", args);
    String meterName = args.meterName();
    Meter meter = lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "counter", args.unit(), args.description());
    LongCounter counter =
        meter
            .counterBuilder(args.name())
            .setUnit(args.unit())
            .setDescription(args.description())
            .build();
    instruments.put(instrumentKey, counter);
  }

  @PostMapping("create_updowncounter")
  public void createUpDownCounter(@RequestBody CreateUpDownCounterArgs args) {
    LOGGER.info("Creating OTel up-down counter: {}", args);
    String meterName = args.meterName();
    Meter meter = lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "updowncounter", args.unit(), args.description());
    LongUpDownCounter upDownCounter =
        meter
            .upDownCounterBuilder(args.name())
            .setUnit(args.unit())
            .setDescription(args.description())
            .build();
    instruments.put(instrumentKey, upDownCounter);
  }

  @PostMapping("create_gauge")
  public void createGauge(@RequestBody CreateGaugeArgs args) {
    LOGGER.info("Creating OTel gauge: {}", args);
    String meterName = args.meterName();
    Meter meter = lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "gauge", args.unit(), args.description());
    DoubleGauge gauge =
        meter
            .gaugeBuilder(args.name())
            .setUnit(args.unit())
            .setDescription(args.description())
            .build();
    instruments.put(instrumentKey, gauge);
  }

  @PostMapping("counter_add")
  public void counterAdd(@RequestBody CounterAddArgs args) {
    LOGGER.info("Adding value to OTel counter : {}", args);
    String meterName = args.meterName();
    lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "counter", args.unit(), args.description());
    LongCounter counter = lookupInstrument(instrumentKey, LongCounter.class);
    counter.add(args.value().longValue(), fromMap(args.attributes()));
  }

  @PostMapping("updowncounter_add")
  public void upDownCounterAdd(@RequestBody UpDownCounterAddArgs args) {
    LOGGER.info("Adding value to OTel up-down counter: {}", args);
    String meterName = args.meterName();
    lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "updowncounter", args.unit(), args.description());
    LongUpDownCounter upDownCounter = lookupInstrument(instrumentKey, LongUpDownCounter.class);
    upDownCounter.add(args.value().longValue(), fromMap(args.attributes()));
  }

  @PostMapping("gauge_record")
  public void gaugeRecord(@RequestBody GaugeRecordArgs args) {
    LOGGER.info("Recording value to OTel gauge: {}", args);
    String meterName = args.meterName();
    lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "gauge", args.unit(), args.description());
    DoubleGauge gauge = lookupInstrument(instrumentKey, DoubleGauge.class);
    gauge.set(args.value().longValue(), fromMap(args.attributes()));
  }

  @PostMapping("create_asynchronous_counter")
  public void createAsynchronousCounter(@RequestBody CreateAsynchronousCounterArgs args) {
    LOGGER.info("Creating OTel asynchronous counter: {}", args);
    String meterName = args.meterName();
    Meter meter = lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(
            meterName, args.name(), "observable_counter", args.unit(), args.description());
    Consumer<ObservableLongMeasurement> observeCallback =
        measurement -> measurement.record(args.value().longValue(), fromMap(args.attributes()));
    ObservableLongCounter observableCounter =
        meter
            .counterBuilder(args.name())
            .setUnit(args.unit())
            .setDescription(args.description())
            .buildWithCallback(observeCallback);
    instruments.put(instrumentKey, observableCounter);
  }

  @PostMapping("create_asynchronous_updowncounter")
  public void createAsynchronousUpDownCounter(
      @RequestBody CreateAsynchronousUpDownCounterArgs args) {
    LOGGER.info("Creating OTel asynchronous up-down counter: {}", args);
    String meterName = args.meterName();
    Meter meter = lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(
            meterName, args.name(), "observable_updowncounter", args.unit(), args.description());
    Consumer<ObservableLongMeasurement> observeCallback =
        measurement -> measurement.record(args.value().longValue(), fromMap(args.attributes()));
    ObservableLongUpDownCounter observableUpDownCounter =
        meter
            .upDownCounterBuilder(args.name())
            .setUnit(args.unit())
            .setDescription(args.description())
            .buildWithCallback(observeCallback);
    instruments.put(instrumentKey, observableUpDownCounter);
  }

  @PostMapping("create_asynchronous_gauge")
  public void createAsynchronousGauge(@RequestBody CreateAsynchronousGaugeArgs args) {
    LOGGER.info("Creating OTel asynchronous gauge: {}", args);
    String meterName = args.meterName();
    Meter meter = lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "observable_gauge", args.unit(), args.description());
    Consumer<ObservableDoubleMeasurement> observeCallback =
        measurement -> measurement.record(args.value().doubleValue(), fromMap(args.attributes()));
    ObservableDoubleGauge observableGauge =
        meter
            .gaugeBuilder(args.name())
            .setUnit(args.unit())
            .setDescription(args.description())
            .buildWithCallback(observeCallback);
    instruments.put(instrumentKey, observableGauge);
  }

  @PostMapping("create_histogram")
  public void createHistogram(@RequestBody CreateHistogramArgs args) {
    LOGGER.info("Creating OTel histogram: {}", args);
    String meterName = args.meterName();
    Meter meter = lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "histogram", args.unit(), args.description());
    DoubleHistogram histogram =
        meter
            .histogramBuilder(args.name())
            .setUnit(args.unit())
            .setDescription(args.description())
            .build();
    instruments.put(instrumentKey, histogram);
  }

  @PostMapping("histogram_record")
  public void histogramRecord(@RequestBody HistogramRecordArgs args) {
    LOGGER.info("Recording value to OTel histogram: {}", args);
    String meterName = args.meterName();
    lookupMeter(meterName);
    String instrumentKey =
        instrumentKey(meterName, args.name(), "histogram", args.unit(), args.description());
    DoubleHistogram histogram = lookupInstrument(instrumentKey, DoubleHistogram.class);
    histogram.record(args.value().longValue(), fromMap(args.attributes()));
  }

  @PostMapping("force_flush")
  public FlushResult forceFlush(@RequestBody FlushArgs args) {
    LOGGER.info("Flushing OTel metrics: {}", args);
    try {
      // TODO: call internal hook to flush metrics
      return new FlushResult(true);
    } catch (Exception e) {
      LOGGER.warn("Failed to flush OTel metrics", e);
      return new FlushResult(false);
    }
  }

  /** Builds {@link Attributes} from a map of strings. */
  private static Attributes fromMap(Map<String, String> map) {
    AttributesBuilder builder = Attributes.builder();
    for (Map.Entry<String, String> entry : map.entrySet()) {
      builder.put(entry.getKey(), entry.getValue());
    }
    return builder.build();
  }

  private Meter lookupMeter(String meterName) {
    Meter meter = meters.get(meterName);
    if (meter == null) {
      throw new IllegalStateException(
          "Meter " + meterName + " not found in registered meters " + meters.keySet());
    }
    return meter;
  }

  private <T> T lookupInstrument(String instrumentKey, Class<T> instrumentType) {
    Object instrument = instruments.get(instrumentKey);
    if (instrument == null) {
      throw new IllegalStateException(
          "Instrument "
              + instrumentKey
              + " not found in registered instruments "
              + instruments.keySet());
    }
    return instrumentType.cast(instrument);
  }

  private static String instrumentKey(
      String meterName, String name, String kind, String unit, String description) {
    return "Meter="
        + meterName
        + ", Name="
        + name.toLowerCase(Locale.ROOT)
        + ", Kind="
        + kind
        + ", Unit="
        + unit
        + ", Description="
        + description;
  }
}
