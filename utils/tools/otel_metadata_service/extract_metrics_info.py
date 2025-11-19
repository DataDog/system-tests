"""
Extract key information from PostgreSQL metrics.
Shows: name, description, type (sum/gauge), and enabled status.
"""
from otel_metadata_fetcher import OTelMetadataFetcher
from typing import Optional
import json


def print_metrics_table(metrics_dict: dict, enabled_only: bool = False) -> None:
    """Print metrics in a nice table format."""
    print(f"\n{'='*120}")
    print(f"PostgreSQL Metrics Summary ({len(metrics_dict)} metrics)")
    print(f"{'='*120}")
    print(f"{'Name':<40} {'Type':<10} {'Description':<70}")
    print(f"{'-'*120}")
    
    for name in sorted(metrics_dict.keys()):
        metric = metrics_dict[name]
        name_display = name[:38]
        metric_type = metric["data_type"]
        description = metric["description"][:68]
        
        print(f"{name_display:<40} {metric_type:<10} {description:<70}")
    
    print(f"{'='*120}\n")


def main() -> None:
    """Main function to extract and display metrics information."""
    
    print("Fetching PostgreSQL receiver metadata from GitHub...")
    
    with OTelMetadataFetcher() as fetcher:
        # Get metrics summary
        metrics_summary = fetcher.get_metrics_summary()
        
        # Get full metrics for enabled/disabled count
        all_metrics = fetcher.get_metrics()
        
        # Print summary statistics
        total = len(metrics_summary)
        enabled = sum(1 for config in all_metrics.values() if config.get("enabled", False))
        disabled = total - enabled
        sum_metrics = sum(1 for m in metrics_summary.values() if m["data_type"] == "Sum")
        gauge_metrics = sum(1 for m in metrics_summary.values() if m["data_type"] == "Gauge")
        
        print(f"\n📊 Statistics:")
        print(f"  Total metrics: {total}")
        print(f"  Enabled: {enabled}")
        print(f"  Disabled: {disabled}")
        print(f"  Sum metrics: {sum_metrics}")
        print(f"  Gauge metrics: {gauge_metrics}")
        
        # Print all metrics
        print("\n📋 All Metrics:")
        print_metrics_table(metrics_summary, enabled_only=False)
        
        # Save to JSON file
        output_file = "postgres_metrics_summary.json"
        with open(output_file, "w") as f:
            json.dump(metrics_summary, f, indent=2)
        print(f"💾 Full data saved to: {output_file}")
        
        # Example: Get specific metrics by type
        print("\n🔍 Example Queries:")
        print("\nSum metrics (first 5):")
        sum_metrics_list = [(name, info) for name, info in metrics_summary.items() if info["data_type"] == "Sum"]
        for name, info in sum_metrics_list[:5]:
            print(f"  - {name}: {info['description']}")
        
        print("\nGauge metrics (first 5):")
        gauge_metrics_list = [(name, info) for name, info in metrics_summary.items() if info["data_type"] == "Gauge"]
        for name, info in gauge_metrics_list[:5]:
            print(f"  - {name}: {info['description']}")


if __name__ == "__main__":
    main()

