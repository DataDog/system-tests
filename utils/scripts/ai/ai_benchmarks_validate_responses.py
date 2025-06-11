#!/usr/bin/env python3
"""Response validation script for system-tests AI benchmarks.
This script validates the responses in logs/responses.txt against the expected patterns
defined in AI_Benchmarks_validations.txt.

Validation Pattern Syntax:
- [pattern]: Single pattern that must be present in the response
- [value1|value2|value3]: Alternative values - any one of the values separated by | is valid
  Example: [framework|workbench] means either "framework" OR "workbench" is acceptable

Usage:
    python ai_benchmark_validate_responses.py
    python ai_benchmark_validate_responses.py end_to_end
    python ai_benchmark_validate_responses.py --validation-type end_to_end
"""

import re
import argparse
from pathlib import Path
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint


@dataclass
class ValidationResult:
    """Class to store validation results for a question."""

    question: str
    expected_patterns: list[str]
    response: str
    matches: list[tuple[str, bool]]
    is_valid: bool


def read_validation_file(file_path: Path) -> dict[str, list[str]]:
    """Read the validation file and return a dictionary of questions and their expected patterns."""
    validations: dict[str, list[str]] = {}
    current_question = None

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped_line = line.strip()
            if not stripped_line:
                continue

            if stripped_line.startswith("Q"):
                # Extract question text after the number and colon
                current_question = (
                    stripped_line.split(":", 1)[1].strip()
                    if len(stripped_line.split(":", 1)) > 1
                    else stripped_line[1:].strip()
                )
            elif stripped_line.startswith("A") and current_question:
                # Extract patterns between square brackets
                patterns = re.findall(r"\[(.*?)\]", stripped_line)
                validations[current_question] = patterns

    return validations


def read_responses_file(file_path: Path) -> dict[str, str]:
    """Read the responses file and return a dictionary of questions and their responses."""
    responses: dict[str, str] = {}
    current_question = None
    current_response: list[str] = []
    in_response = False

    console = Console()
    console.print("\n[bold yellow]Debug: Reading responses file[/bold yellow]")

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            original_line = line
            stripped_line = line.strip()

            if not stripped_line:
                console.print(f"[dim]Skipping empty line {line_num}[/dim]")
                continue

            # Only skip lines starting with # if they look like actual comments
            # (not markdown headers which are part of responses)
            if stripped_line.startswith("#") and not any(
                char in stripped_line for char in ["*", "🚀", "⚡", "🔧", "☸️"]
            ):
                console.print(f"[dim]Skipping comment line {line_num}: {original_line.strip()}[/dim]")
                continue

            if stripped_line.startswith("Q"):
                if current_question and current_response:
                    response_text = " ".join(current_response)
                    console.print(f"[green]Storing response for question: {current_question}[/green]")
                    console.print(f"[dim]Response text: {response_text}[/dim]")
                    responses[current_question] = response_text

                # Extract question text after the number and colon
                question_parts = stripped_line.split(":", 1)
                current_question = question_parts[1].strip() if len(question_parts) > 1 else stripped_line[1:].strip()
                console.print(f"[blue]Found question: {current_question}[/blue]")
                current_response = []
                in_response = False

            elif stripped_line.startswith("A") and current_question:
                # Extract response text after the number and colon
                response_parts = stripped_line.split(":", 1)
                response_text = response_parts[1].strip() if len(response_parts) > 1 else stripped_line[1:].strip()
                console.print(f"[yellow]Found answer start: {response_text}[/yellow]")
                current_response.append(response_text)
                in_response = True

            elif in_response and current_question:
                # Skip empty lines in the middle of responses
                if stripped_line:
                    console.print(f"[dim]Adding to response: {stripped_line}[/dim]")
                    current_response.append(stripped_line)

    if current_question and current_response:
        response_text = " ".join(current_response)
        console.print(f"[green]Storing final response for question: {current_question}[/green]")
        console.print(f"[dim]Response text: {response_text}[/dim]")
        responses[current_question] = response_text

    console.print("\n[bold yellow]Final responses dictionary:[/bold yellow]")
    for q, r in responses.items():
        console.print(f"[blue]Q: {q}[/blue]")
        console.print(f"[green]A: {r}[/green]")
        console.print("---")

    return responses


def normalize_text(text: str) -> str:
    """Normalize text for comparison by removing extra spaces, converting to lowercase, and removing extra text."""
    # Remove any question numbers (e.g., "Q1:", "Q2:")
    text = re.sub(r"^Q\d*:", "", text)
    # Remove any answer numbers (e.g., "A1:", "A2:")
    text = re.sub(r"^A\d*:", "", text)
    # Remove any extra text after the main question
    text = re.sub(r"\s*Check.*$", "", text)
    # Normalize spaces and convert to lowercase
    return " ".join(text.lower().split())


def validate_responses(validations: dict[str, list[str]], responses: dict[str, str]) -> list[ValidationResult]:
    """Validate responses against expected patterns."""
    results = []

    # Create normalized versions of questions for matching
    normalized_validations = {normalize_text(q): (q, p) for q, p in validations.items()}
    normalized_responses = {normalize_text(q): (q, r) for q, r in responses.items()}

    # Debug information
    console = Console()
    console.print("\n[bold yellow]Normalized Questions:[/bold yellow]")
    console.print("\n[bold]Validation Questions:[/bold]")
    for norm_q, (orig_q, _) in normalized_validations.items():
        console.print(f"  - Original: '{orig_q}'")
        console.print(f"    Normalized: '{norm_q}'")
    console.print("\n[bold]Response Questions:[/bold]")
    for norm_q, (orig_q, _) in normalized_responses.items():
        console.print(f"  - Original: '{orig_q}'")
        console.print(f"    Normalized: '{norm_q}'")

    for norm_val_q, (val_q, patterns) in normalized_validations.items():
        response = ""
        if norm_val_q in normalized_responses:
            response = normalized_responses[norm_val_q][1]

        matches = []
        is_valid = True

        for pattern in patterns:
            # Check if pattern contains alternative values (value1|value2|value3)
            if "|" in pattern:
                # Split by | to get alternative values
                alternatives = [alt.strip() for alt in pattern.split("|")]
                pattern_match = False

                # Check if any of the alternatives match
                for alternative in alternatives:
                    if check_pattern_match(alternative, response):
                        pattern_match = True
                        break

                matches.append((pattern, pattern_match))
                if not pattern_match:
                    is_valid = False
            else:
                # Original logic for single patterns
                pattern_match = check_pattern_match(pattern, response)
                matches.append((pattern, pattern_match))
                if not pattern_match:
                    is_valid = False

        results.append(
            ValidationResult(
                question=val_q, expected_patterns=patterns, response=response, matches=matches, is_valid=is_valid
            )
        )

    return results


def check_pattern_match(pattern: str, response: str) -> bool:
    """Check if a single pattern matches the response."""
    # Check if all words in the pattern are present in the response
    pattern_words = pattern.lower().split()
    response_lower = response.lower()

    # More flexible matching: allow for word variations and partial matches
    for word in pattern_words:
        # Remove punctuation and special characters for comparison
        word_clean = re.sub(r"[^\w\s]", "", word)
        response_clean = re.sub(r"[^\w\s]", "", response_lower)

        # Check if the word or its variations are present
        if not any(word_clean in w for w in response_clean.split()):
            return False

    return True


def print_validation_report(results: list[ValidationResult]) -> None:
    """Print a fancy validation report using rich."""
    console = Console()

    # Print header
    console.print(Panel.fit("[bold blue]System Tests AI Response Validation Report[/bold blue]", border_style="blue"))

    # Create summary table
    summary_table = Table(title="Validation Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Question", style="cyan")
    summary_table.add_column("Status", style="green")
    summary_table.add_column("Missing Patterns", style="red")

    for result in results:
        missing_patterns = [pattern for pattern, match in result.matches if not match]
        status = "[green]✓[/green]" if result.is_valid else "[red]✗[/red]"
        missing = "\n".join(missing_patterns) if missing_patterns else "None"
        summary_table.add_row(result.question, status, missing)

    console.print(summary_table)

    # Print detailed results
    for result in results:
        console.print(
            Panel(
                f"[bold]Question:[/bold] {result.question}\n"
                f"[bold]Response:[/bold] {result.response}\n"
                f"[bold]Validation:[/bold] {'[green]PASS[/green]' if result.is_valid else '[red]FAIL[/red]'}\n"
                f"[bold]Pattern Matches:[/bold]\n"
                + "\n".join(
                    f"  {'[green]✓[/green]' if match else '[red]✗[/red]'} {pattern}"
                    for pattern, match in result.matches
                ),
                title="Detailed Results",
                border_style="blue" if result.is_valid else "red",
            )
        )


def main() -> None:
    """Main function to run the validation."""
    parser = argparse.ArgumentParser(
        description="Validate AI benchmark responses against expected patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ai_benchmark_validate_responses.py
  python ai_benchmark_validate_responses.py end_to_end
  python ai_benchmark_validate_responses.py --validation-type parametric
        """,
    )
    parser.add_argument(
        "validation_type",
        nargs="?",
        default="",
        help=(
            "Type of validation to use (e.g., 'end_to_end', 'parametric'). "
            "If not specified, uses default validation file."
        ),
    )
    parser.add_argument(
        "--validation-type",
        dest="validation_type_flag",
        help="Alternative way to specify validation type using flag format",
    )

    args = parser.parse_args()

    # Determine validation type (prioritize flag over positional argument)
    validation_type = args.validation_type_flag or args.validation_type

    script_dir = Path(__file__).parent

    # Construct validation file path based on validation type
    if validation_type:
        validation_file = script_dir / f"ai_benchmarks_{validation_type}_validations.txt"
    else:
        validation_file = script_dir / "ai_benchmarks_validations.txt"

    responses_file = Path("logs/responses.txt")

    if not validation_file.exists():
        rprint(f"[red]Error: Validation file not found at {validation_file}[/red]")
        return

    if not responses_file.exists():
        rprint(f"[red]Error: Responses file not found at {responses_file}[/red]")
        return

    # Print which validation file is being used
    console = Console()
    console.print(f"[bold yellow]Using validation file:[/bold yellow] {validation_file}")

    validations = read_validation_file(validation_file)
    responses = read_responses_file(responses_file)

    # Debug information
    console.print("\n[bold yellow]Debug Information:[/bold yellow]")
    console.print("\n[bold]Validation Questions:[/bold]")
    for q in validations:
        console.print(f"  - '{q}'")
    console.print("\n[bold]Response Questions:[/bold]")
    for q in responses:
        console.print(f"  - '{q}'")

    results = validate_responses(validations, responses)
    print_validation_report(results)


if __name__ == "__main__":
    main()
