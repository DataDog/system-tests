#!/usr/bin/env python3
"""
Fetch PostgreSQL receiver metrics from OpenTelemetry Collector Contrib.

This simple script:
1. Fetches metadata.yaml from GitHub
2. Parses it to extract metrics
3. Saves to postgres_metrics.json in the test directory

Usage:
    python fetch_otel_postgres_metrics.py
"""
import httpx
import yaml
import json
from pathlib import Path
from typing import Dict, Any


def fetch_postgres_metadata(ref: str = "main") -> Dict[str, Any]:
    """
    Fetch PostgreSQL receiver metadata from GitHub.
    
    Args:
        ref: Git reference (branch, tag, or commit SHA). Defaults to 'main'.
    
    Returns:
        Parsed YAML metadata as dictionary
    """
    url = (
        f"https://raw.githubusercontent.com/open-telemetry/"
        f"opentelemetry-collector-contrib/{ref}/"
        f"receiver/postgresqlreceiver/metadata.yaml"
    )
    
    print(f"📡 Fetching from: {url}")
    
    try:
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return yaml.safe_load(response.text)
    except Exception as e:
        print(f"❌ Error fetching metadata: {e}")
        raise


def extract_metrics_summary(metadata: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Extract metrics summary from metadata.
    
    Args:
        metadata: Full metadata dictionary
    
    Returns:
        Dictionary mapping metric names to {data_type, description}
    """
    metrics = metadata.get("metrics", {})
    summary = {}
    
    for name, config in metrics.items():
        # Determine metric type (Sum, Gauge, Histogram, etc.)
        metric_type = "Unknown"
        if "sum" in config:
            metric_type = "Sum"
        elif "gauge" in config:
            metric_type = "Gauge"
        elif "histogram" in config:
            metric_type = "Histogram"
        
        summary[name] = {
            "data_type": metric_type,
            "description": config.get("description", "No description"),
        }
    
    return summary


def save_metrics(metrics: Dict[str, Any], output_path: Path) -> None:
    """Save metrics to JSON file."""
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"💾 Saved {len(metrics)} metrics to: {output_path}")


def main() -> None:
    """Main function."""
    print("=" * 80)
    print("PostgreSQL Metrics Fetcher")
    print("=" * 80)
    
    # Fetch metadata from GitHub
    metadata = fetch_postgres_metadata(ref="main")
    print(f"✓ Fetched metadata from OpenTelemetry Collector Contrib")
    
    # Extract metrics summary
    metrics_summary = extract_metrics_summary(metadata)
    print(f"✓ Extracted {len(metrics_summary)} metrics")
    
    # Save to test directory
    script_dir = Path(__file__).parent
    output_path = script_dir.parent.parent / "tests/otel_postgres_metrics_e2e/postgres_metrics.json"
    save_metrics(metrics_summary, output_path)
    
    print("\n" + "=" * 80)
    print("✓ Done! The test file will automatically load this JSON.")
    print("=" * 80)
    
    # Show sample
    print("\nSample metrics:")
    for i, (name, info) in enumerate(list(metrics_summary.items())[:3]):
        print(f"  {name}:")
        print(f"    data_type: {info['data_type']}")
        print(f"    description: {info['description']}")
        if i < 2:
            print()


if __name__ == "__main__":
    main()

