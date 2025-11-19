#!/usr/bin/env python3
"""
Update postgres_metrics.json from the OTel metadata service.

This script:
1. Fetches metrics from http://localhost:8080/api/v1/metrics/summary
2. Writes the output to postgres_metrics.json

Usage in test files:
    import json
    with open("postgres_metrics.json") as f:
        postgresql_metrics = json.load(f)
"""
import httpx
import json
from pathlib import Path
from typing import Dict, Any


def fetch_metrics(base_url: str = "http://localhost:8080") -> Dict[str, Any]:
    """Fetch metrics from the service."""
    url = f"{base_url}/api/v1/metrics/summary"
    print(f"📡 Fetching metrics from: {url}")
    
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        print("❌ Error: Could not connect to the service.")
        print("   Make sure the service is running: python main.py")
        raise
    except httpx.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        raise


def save_to_file(metrics: Dict[str, Any], output_file: str = "postgres_metrics.json") -> Path:
    """Save metrics to a JSON file."""
    output_path = Path(output_file)
    
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"💾 Saved {len(metrics)} metrics to: {output_path.absolute()}")
    return output_path


def main() -> None:
    """Main function to update postgres_metrics.json."""
    print("=" * 80)
    print("PostgreSQL Metrics Updater")
    print("=" * 80)
    
    # Step 1: Fetch metrics
    metrics = fetch_metrics()
    print(f"✓ Fetched {len(metrics)} metrics")
    
    # Step 2: Save to file
    output_file = save_to_file(metrics)
    
    print("\n" + "=" * 80)
    print("✓ Done! Use in your test file:")
    print("=" * 80)
    print("""
import json
from pathlib import Path

# Load the metrics
metrics_file = Path(__file__).parent / "postgres_metrics.json"
with open(metrics_file) as f:
    postgresql_metrics = json.load(f)
""")
    print("=" * 80)


if __name__ == "__main__":
    main()

