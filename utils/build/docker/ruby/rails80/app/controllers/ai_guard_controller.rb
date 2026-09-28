# frozen_string_literal: true

class AiGuardController < ApplicationController
  skip_before_action :verify_authenticity_token

  def evaluate
    messages = params.to_unsafe_h.fetch(:_json).map do |message_data|
      tool_calls = message_data.fetch(:tool_calls, []).map do |tool_call_data|
        Datadog::AIGuard.tool_call(
          id: tool_call_data[:id],
          name: tool_call_data.dig(:function, :name),
          arguments: tool_call_data.dig(:function, :arguments)
        )
      end

      if message_data[:content].is_a?(Array)
        Datadog::AIGuard.message(
          role: message_data[:role],
          tool_calls: tool_calls,
          tool_call_id: message_data[:tool_call_id]
        ) do |message|
          message_data[:content].each do |part|
            case part[:type]
            when 'text'
              message.text(part[:text])
            when 'image_url'
              message.image_url(part.dig(:image_url, :url))
            end
          end
        end
      else
        Datadog::AIGuard.message(
          role: message_data[:role],
          content: message_data[:content],
          tool_calls: tool_calls,
          tool_call_id: message_data[:tool_call_id]
        )
      end
    end

    user_id = request.headers['X-User-Id']
    session_id = request.headers['X-Session-Id']
    Datadog::Kit::Identity.set_user(id: user_id, session_id: session_id) if user_id.present? && session_id.present?

    allow_raise = request.headers['X-AI-Guard-Block']&.downcase == 'true'
    result = Datadog::AIGuard.evaluate(*messages, allow_raise: allow_raise)

    response_data = {
      action: result.action,
      reason: result.reason,
      tags: result.tags
    }
    response_data[:tag_probs] = result.tag_probabilities if result.respond_to?(:tag_probabilities)
    response_data[:sds] = result.sds_findings if result.respond_to?(:sds_findings)
    response_data[:messages] = result.messages.map(&:to_h) if result.respond_to?(:messages)
    if result.respond_to?(:redaction_replacements)
      response_data[:redaction_replacements] = result.redaction_replacements
    end
    render json: response_data
  rescue Datadog::AIGuard::AIGuardAbortError => e
    error_data = { action: e.action, reason: e.reason, tags: e.tags }
    error_data[:tag_probabilities] = e.tag_probabilities if e.respond_to?(:tag_probabilities)
    error_data[:sds_findings] = e.sds_findings if e.respond_to?(:sds_findings)
    render json: error_data, status: 403
  rescue StandardError => e
    render json: { error: e.to_s, type: e.class.name }, status: 500
  end
end
