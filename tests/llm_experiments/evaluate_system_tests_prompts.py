"""
POC: Evaluate System-Tests AI Assistant Prompts using Datadog LLM Observability

This script demonstrates how to evaluate AI assistant responses using:
- Datadog LLM Observability Experiments: https://docs.datadoghq.com/llm_observability/experiments/setup/
- Semantic Similarity Evaluator: https://docs.datadoghq.com/llm_observability/guide/evaluation_developer_guide/#semanticsimilarityevaluator
- Dogfooding LLM Experiments: https://datadoghq.atlassian.net/wiki/spaces/MO1/pages/5334368583/Dogfooding+LLM+Experiments

Workflow:
1. Initialize Datadog LLM Observability
2. Load test questions from CSV dataset
3. Run Claude agent with system-tests rules
4. Evaluate responses using semantic similarity
5. View results in Datadog UI
"""

import asyncio
import os
from typing import Any

import numpy as np
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
from ddtrace.llmobs import BaseEvaluator, EvaluatorContext, EvaluatorResult, LLMObs
from dotenv import load_dotenv
from openai import OpenAI

# Load API keys from environment
load_dotenv()


# ============================================================================
# STEP 1: Define Custom Evaluator
# ============================================================================
class SemanticSimilarityEvaluator(BaseEvaluator):
    """
    Evaluates semantic similarity between AI output and expected answer.
    Uses OpenAI embeddings + cosine similarity to measure how close the answer is.
    """

    def __init__(self, openai_client: OpenAI, threshold: float = 0.8) -> None:
        super().__init__(name="semantic_similarity")
        self.threshold = threshold
        self.client = openai_client

    def evaluate(self, context: EvaluatorContext) -> EvaluatorResult:
        """Compare output vs expected using semantic similarity."""
        if not context.expected_output:
            return EvaluatorResult(value=None, reasoning="No expected output", assessment="skipped")

        # Get embeddings for both texts
        output_embedding = self._get_embedding(str(context.output_data))
        expected_embedding = self._get_embedding(str(context.expected_output))

        # Calculate cosine similarity (0-1 score)
        similarity = np.dot(output_embedding, expected_embedding) / (
            np.linalg.norm(output_embedding) * np.linalg.norm(expected_embedding)
        )

        # Return pass/fail based on threshold
        return EvaluatorResult(
            value=float(similarity),
            reasoning=f"Similarity: {similarity:.2%}",
            assessment="pass" if similarity >= self.threshold else "fail",
        )

    def _get_embedding(self, text: str) -> list[float]:
        """Get OpenAI embedding for text."""
        response = self.client.embeddings.create(input=text, model="text-embedding-3-small")
        return response.data[0].embedding


# ============================================================================
# STEP 2: Define Task Function (What to Evaluate)
# ============================================================================
def task(input_data: dict[str, Any], config: dict[str, Any] | None = None) -> str:  # noqa: ARG001
    """
    The task function that processes each question from the dataset.
    Calls Claude agent with system-tests rules and returns the answer.
    """
    question = input_data["question"]

    async def query_claude() -> str:
        # Configure Claude with system-tests rules (loaded from .cursor/rules/)
        options = ClaudeAgentOptions(max_turns=50, model="claude-sonnet-4-5-20250929")

        # Query Claude and collect response
        response_text = ""
        async for message in query(prompt=question, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        return response_text

    return asyncio.run(query_claude())


# ============================================================================
# STEP 3: Main Experiment Runner
# ============================================================================
def main() -> None:
    """Run the LLM Observability experiment."""

    # Initialize Datadog LLM Observability
    LLMObs.enable(
        api_key=os.getenv("DD_API_KEY_ONBOARDING"),
        app_key=os.getenv("DD_APP_KEY_ONBOARDING"),
        site="datadoghq.com",
        project_name="system-tests",
    )
    print("✓ Datadog LLM Observability enabled")  # noqa: T201

    # Load test dataset from CSV
    # Expected format: question,category,answer
    dataset = LLMObs.create_dataset_from_csv(
        csv_path="questions.csv",
        dataset_name="system-tests_end-to-end",
        description="System-tests AI assistant evaluation questions",
        input_data_columns=["question", "category"],
        expected_output_columns=["answer"],
    )
    print("✓ Dataset loaded from questions.csv")  # noqa: T201

    # Initialize evaluator with OpenAI embeddings
    openai_client = OpenAI()
    evaluator = SemanticSimilarityEvaluator(openai_client=openai_client, threshold=0.8)
    print("✓ Semantic similarity evaluator configured (threshold: 80%)")  # noqa: T201

    # Create and configure experiment
    experiment = LLMObs.experiment(
        name="system-tests_end-to-end",
        task=task,  # Function that generates responses
        dataset=dataset,  # Questions to test
        evaluators=[evaluator],  # How to score responses
        description="Evaluating system-tests AI assistant responses",
        config={"model": "claude-sonnet-4-5-20250929"},
    )

    # Run experiment on all dataset records
    print("\n🚀 Running experiment...")  # noqa: T201
    results = experiment.run()

    # Display results summary
    print("\n" + "=" * 80)  # noqa: T201
    print("RESULTS SUMMARY")  # noqa: T201
    print("=" * 80)  # noqa: T201

    for result in results.get("rows", []):
        print(f"\n📝 Question #{result['idx']}")  # noqa: T201
        print(f"   Input: {result['input']}")  # noqa: T201

        # Show truncated output
        output = str(result["output"])
        print(f"   Output: {output[:200]}..." if len(output) > 200 else f"   Output: {output}")  # noqa: T201

        # Show evaluation scores
        for eval_name, eval_data in result.get("evaluations", {}).items():
            value = eval_data.get("value", "N/A")
            assessment = eval_data.get("assessment", "")
            icon = "✓" if assessment == "pass" else "✗" if assessment == "fail" else "⊘"
            print(f"   {icon} {eval_name}: {value} ({assessment})")  # noqa: T201

        # Show errors if any
        if result.get("error", {}).get("message"):
            print(f"   ❌ Error: {result['error']['message']}")  # noqa: T201

    # Provide link to Datadog UI
    print("\n" + "=" * 80)  # noqa: T201
    print(f"📊 View detailed results: {experiment.url}")  # noqa: T201
    print("=" * 80 + "\n")  # noqa: T201


if __name__ == "__main__":
    main()
