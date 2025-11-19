"""
Basic tests for the OTel metadata fetcher.
Run with: pytest test_otel_fetcher.py -v
"""
import pytest
from otel_metadata_fetcher import OTelMetadataFetcher, get_postgres_metrics


def test_fetch_postgres_metadata() -> None:
    """Test fetching the full PostgreSQL metadata."""
    with OTelMetadataFetcher() as fetcher:
        metadata = fetcher.fetch_postgres_metadata()
        
        assert metadata is not None
        assert "metrics" in metadata
        assert "resource_attributes" in metadata
        assert "attributes" in metadata
        assert "events" in metadata


def test_get_metrics() -> None:
    """Test getting all metrics."""
    with OTelMetadataFetcher() as fetcher:
        metrics = fetcher.get_metrics()
        
        assert isinstance(metrics, dict)
        assert len(metrics) > 0
        
        # Check for some known metrics
        assert "postgresql.backends" in metrics
        assert "postgresql.db_size" in metrics
        assert "postgresql.commits" in metrics


def test_get_enabled_metrics() -> None:
    """Test getting only enabled metrics."""
    with OTelMetadataFetcher() as fetcher:
        enabled_metrics = fetcher.get_enabled_metrics()
        
        assert isinstance(enabled_metrics, dict)
        assert len(enabled_metrics) > 0
        
        # All returned metrics should be enabled
        for metric_name, metric_config in enabled_metrics.items():
            assert metric_config.get("enabled") is True


def test_get_metric_by_name() -> None:
    """Test getting a specific metric by name."""
    with OTelMetadataFetcher() as fetcher:
        metric = fetcher.get_metric_by_name("postgresql.backends")
        
        assert metric is not None
        assert "description" in metric
        assert "enabled" in metric
        assert metric["enabled"] is True
        
        # Test non-existent metric
        non_existent = fetcher.get_metric_by_name("postgresql.does_not_exist")
        assert non_existent is None


def test_get_resource_attributes() -> None:
    """Test getting resource attributes."""
    with OTelMetadataFetcher() as fetcher:
        attrs = fetcher.get_resource_attributes()
        
        assert isinstance(attrs, dict)
        assert len(attrs) > 0
        
        # Check for known resource attributes
        assert "postgresql.database.name" in attrs
        assert "postgresql.table.name" in attrs


def test_get_attributes() -> None:
    """Test getting attributes."""
    with OTelMetadataFetcher() as fetcher:
        attrs = fetcher.get_attributes()
        
        assert isinstance(attrs, dict)
        assert len(attrs) > 0


def test_get_events() -> None:
    """Test getting events."""
    with OTelMetadataFetcher() as fetcher:
        events = fetcher.get_events()
        
        assert isinstance(events, dict)
        assert len(events) > 0
        
        # Check for known events
        assert "db.server.query_sample" in events
        assert "db.server.top_query" in events


def test_convenience_function() -> None:
    """Test the convenience function."""
    metrics = get_postgres_metrics()
    
    assert isinstance(metrics, dict)
    assert len(metrics) > 0
    assert "postgresql.backends" in metrics


def test_custom_commit_sha() -> None:
    """Test using a custom commit SHA."""
    # Using the same commit SHA as default, should work
    custom_sha = "270e3cb8cdfe619322be1af2b49a0901d8188a9c"
    
    with OTelMetadataFetcher(commit_sha=custom_sha) as fetcher:
        metrics = fetcher.get_metrics()
        
        assert isinstance(metrics, dict)
        assert len(metrics) > 0


def test_metric_structure() -> None:
    """Test that metrics have expected structure."""
    with OTelMetadataFetcher() as fetcher:
        metric = fetcher.get_metric_by_name("postgresql.backends")
        
        assert metric is not None
        assert "description" in metric
        assert "enabled" in metric
        assert "unit" in metric
        assert "stability" in metric
        
        # Check nested structure
        if "sum" in metric:
            assert "value_type" in metric["sum"]
            assert "aggregation_temporality" in metric["sum"]


def test_event_structure() -> None:
    """Test that events have expected structure."""
    with OTelMetadataFetcher() as fetcher:
        events = fetcher.get_events()
        query_sample = events.get("db.server.query_sample")
        
        assert query_sample is not None
        assert "enabled" in query_sample
        assert "description" in query_sample
        assert "attributes" in query_sample
        assert isinstance(query_sample["attributes"], list)
        assert len(query_sample["attributes"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

