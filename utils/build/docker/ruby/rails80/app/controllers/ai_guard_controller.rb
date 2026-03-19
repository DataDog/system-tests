
# frozen_string_literal: true

class AiGuardController < ApplicationController
  skip_before_action :verify_authenticity_token

  def evaluate
    messages = params.to_unsafe_h.fetch(:_json).flat_map do |message_data|
      if message_data[:tool_calls]
        message_data[:tool_calls].map do |tool_call_data|
          Datadog::AIGuard.assistant(
            id: tool_call_data[:id],
            tool_name: tool_call_data.dig(:function, :name),
            arguments: tool_call_data.dig(:function, :arguments)
          )
        end
      elsif message_data[:tool_call_id]
        Datadog::AIGuard.tool(tool_call_id: message_data[:tool_call_id], content: message_data[:content])
      else
        Datadog::AIGuard.message(role: message_data[:role], content: message_data[:content])
      end
    end

    allow_raise = request.headers['X-AI-Guard-Block']&.downcase == "true"
    result = Datadog::AIGuard.evaluate(*messages, allow_raise: allow_raise)

    response_data = {
      action: result.action,
      reason: result.reason,
      tags: result.tags,
      is_blocking_enabled: result.blocking_enabled?
    }
    response_data[:sds] = result.sds if result.respond_to?(:sds)
    render json: response_data
  rescue Datadog::AIGuard::AIGuardAbortError => e
    error_data = { action: e.action, reason: e.reason, tags: e.tags }
    error_data[:sds] = e.sds if e.respond_to?(:sds)
    render json: error_data, status: 403
  rescue => e
    render json: {error: e.to_s, type: e.class.name}, status: 500
  end
end
