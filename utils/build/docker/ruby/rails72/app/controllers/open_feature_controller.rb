# frozen_string_literal: true

class OpenFeatureController < ApplicationController
  skip_before_action :verify_authenticity_token

  def start
    OpenFeature::SDK.set_provider(Datadog::OpenFeature::Provider.new)

    # NOTE: There is no set_provider_and_wait in OpenFeature::SDK
    loop do
      break unless Datadog::OpenFeature.evaluator.ufc_json.nil?
      sleep 0.1
    end

    render json: {}
  end

  def evaluate
    payload = JSON.parse(request.body.string)

    render json: evaluate_payload(payload)
  end

  def fork_isolation
    payload = JSON.parse(request.body.string)
    parent_payload = payload.merge(
      'flag' => payload['parentFlag'],
      'targetingKey' => payload['parentTargetingKey'] || 'evp-prefork-parent'
    )
    child_payload = payload.merge(
      'flag' => payload['childFlag'],
      'targetingKey' => payload['childTargetingKey'] || 'evp-prefork-child'
    )

    parent_result = evaluate_payload(parent_payload)
    child_result = evaluate_in_fork(child_payload)

    render json: {parent: parent_result, child: child_result, diagnostics: open_feature_diagnostics}
  end

  private

  def evaluate_payload(payload)
    client = OpenFeature::SDK.build_client

    args = {
      flag: payload['flag'],
      variation_type: payload['variationType'],
      default_value: payload['defaultValue'],
      targeting_key: payload['targetingKey'],
      targeting_keys: payload['targetingKeys'],
      attributes: payload['attributes']
    }

    begin
      targeting_keys =
        if args[:targeting_keys].is_a?(Array) && !args[:targeting_keys].empty?
          args[:targeting_keys]
        else
          [args[:targeting_key]]
        end
      value = nil

      targeting_keys.each do |targeting_key|
        context = OpenFeature::SDK::EvaluationContext.new(
          targeting_key: targeting_key, **args[:attributes]
        )
        options = {
          flag_key: args[:flag], default_value: args[:default_value], evaluation_context: context
        }

        value =
          case args[:variation_type]
          when 'BOOLEAN' then client.fetch_boolean_value(**options)
          when 'STRING' then client.fetch_string_value(**options)
          when 'INTEGER' then client.fetch_integer_value(**options)
          when 'NUMERIC' then client.fetch_float_value(**options)
          when 'JSON' then client.fetch_object_value(**options)
          else 'FATAL_UNEXPECTED_VARIATION_TYPE'
          end
      end

      {value: value, reason: 'DEFAULT', count: targeting_keys.length}
    rescue
      {value: args[:default_value], reason: 'ERROR'}
    end
  end

  def evaluate_in_fork(payload)
    return {value: payload['defaultValue'], reason: 'ERROR', error: 'fork unavailable'} unless Process.respond_to?(:fork)

    reader, writer = IO.pipe
    pid = Process.fork do
      reader.close
      result = evaluate_payload(payload)
      result[:diagnostics_before_flush] = open_feature_diagnostics
      flush_open_feature
      result[:diagnostics_after_flush] = open_feature_diagnostics
      writer.write(JSON.generate(result))
      writer.close
      exit! 0
    rescue StandardError => e
      writer.write(JSON.generate(value: payload['defaultValue'], reason: 'ERROR', error: "#{e.class}: #{e.message}"))
      exit! 1
    end

    writer.close
    body = reader.read
    _, status = Process.wait2(pid)
    result = body.empty? ? {} : JSON.parse(body)
    result['forkStatus'] = status.exitstatus unless status.success?
    result
  ensure
    reader&.close unless reader&.closed?
    writer&.close unless writer&.closed?
  end

  def flush_open_feature
    open_feature = Datadog.send(:components)&.open_feature
    worker = open_feature&.instance_variable_get(:@worker)
    worker&.send(:send_events, *worker.dequeue)

    writer = open_feature&.instance_variable_get(:@flag_eval_evp_writer)
    writer&.send(:drain_and_flush)
  end

  def open_feature_diagnostics
    open_feature = Datadog.send(:components)&.open_feature
    evp_writer = open_feature&.instance_variable_get(:@flag_eval_evp_writer)
    evp_hook =
      if open_feature&.respond_to?(:flag_eval_evp_hook)
        !open_feature.flag_eval_evp_hook.nil?
      else
        false
      end

    {
      open_feature: !open_feature.nil?,
      evp_hook: evp_hook,
      evp_writer: !evp_writer.nil?,
      evp_writer_class: evp_writer&.class&.name,
      openfeature_hook_api: !!defined?(::OpenFeature::SDK::Hooks::Hook)
    }
  end
end
