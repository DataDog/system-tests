"""
Example usage of the OTel metadata fetcher.
This demonstrates how to use the fetcher outside of the MCP context.
"""
from otel_metadata_fetcher import OTelMetadataFetcher, get_postgres_metrics
import json


def main() -> None:
    """Example usage of the OTel metadata fetcher."""
    
    print("=" * 80)
    print("OpenTelemetry PostgreSQL Receiver Metadata Fetcher - Example Usage")
    print("=" * 80)
    
    # Method 1: Using the convenience function
    print("\n1. Using convenience function to get all metrics:")
    print("-" * 80)
    metrics = get_postgres_metrics()
    print(f"Total metrics found: {len(metrics)}")
    print(f"First metric: {list(metrics.keys())[0]}")
    
    # Method 2: Using the class with context manager
    print("\n2. Using context manager to get enabled metrics:")
    print("-" * 80)
    with OTelMetadataFetcher() as fetcher:
        enabled_metrics = fetcher.get_enabled_metrics()
        print(f"Enabled metrics count: {len(enabled_metrics)}")
        print("\nEnabled metrics:")
        for metric_name in sorted(enabled_metrics.keys()):
            metric_config = enabled_metrics[metric_name]
            unit = metric_config.get("unit", "N/A")
            description = metric_config.get("description", "N/A")
            print(f"  - {metric_name}")
            print(f"    Unit: {unit}")
            print(f"    Description: {description[:80]}...")
    
    # Method 3: Get a specific metric
    print("\n3. Getting a specific metric by name:")
    print("-" * 80)
    with OTelMetadataFetcher() as fetcher:
        metric = fetcher.get_metric_by_name("postgresql.backends")
        if metric:
            print(json.dumps(metric, indent=2))
    
    # Method 4: Get resource attributes
    print("\n4. Getting resource attributes:")
    print("-" * 80)
    with OTelMetadataFetcher() as fetcher:
        resource_attrs = fetcher.get_resource_attributes()
        print(f"Resource attributes count: {len(resource_attrs)}")
        for attr_name, attr_config in resource_attrs.items():
            print(f"  - {attr_name}: {attr_config.get('description', 'N/A')}")
    
    # Method 5: Get events
    print("\n5. Getting events:")
    print("-" * 80)
    with OTelMetadataFetcher() as fetcher:
        events = fetcher.get_events()
        print(f"Events count: {len(events)}")
        for event_name, event_config in events.items():
            print(f"  - {event_name}: {event_config.get('description', 'N/A')}")
            attrs = event_config.get("attributes", [])
            print(f"    Attributes ({len(attrs)}): {', '.join(attrs[:5])}")
    
    # Method 6: Get attributes
    print("\n6. Getting attributes:")
    print("-" * 80)
    with OTelMetadataFetcher() as fetcher:
        attributes = fetcher.get_attributes()
        print(f"Attributes count: {len(attributes)}")
        # Show first 10 attributes
        for attr_name in list(attributes.keys())[:10]:
            attr_config = attributes[attr_name]
            print(f"  - {attr_name}: {attr_config.get('description', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("Example complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()

