"""
Fetcher for OpenTelemetry Collector Contrib metadata files from GitHub.
"""
from typing import Any, Dict, List, Optional
import httpx
import yaml
from functools import lru_cache


class OTelMetadataFetcher:
    """Fetches and parses OpenTelemetry receiver metadata from GitHub."""
    
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com/open-telemetry/opentelemetry-collector-contrib"
    POSTGRES_METADATA_PATH = "receiver/postgresqlreceiver/metadata.yaml"
    
    def __init__(self, ref: str = "main") -> None:
        """
        Initialize the fetcher.
        
        Args:
            ref: Git reference to fetch from - can be branch name (e.g., 'main'), 
                 commit SHA, or tag (defaults to 'main' for latest)
        """
        self.ref = ref
        self.client = httpx.Client(timeout=30.0)
    
    def _build_url(self, file_path: str) -> str:
        """Build the raw GitHub URL for a file."""
        return f"{self.GITHUB_RAW_BASE}/{self.ref}/{file_path}"
    
    @lru_cache(maxsize=10)
    def fetch_postgres_metadata(self) -> Dict[str, Any]:
        """
        Fetch and parse the PostgreSQL receiver metadata YAML.
        
        Returns:
            Parsed YAML as a dictionary
            
        Raises:
            httpx.HTTPError: If the request fails
            yaml.YAMLError: If parsing fails
        """
        url = self._build_url(self.POSTGRES_METADATA_PATH)
        response = self.client.get(url)
        response.raise_for_status()
        
        return yaml.safe_load(response.text)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all PostgreSQL metrics definitions."""
        metadata = self.fetch_postgres_metadata()
        return metadata.get("metrics", {})
    
    def get_resource_attributes(self) -> Dict[str, Any]:
        """Get all PostgreSQL resource attributes."""
        metadata = self.fetch_postgres_metadata()
        return metadata.get("resource_attributes", {})
    
    def get_attributes(self) -> Dict[str, Any]:
        """Get all PostgreSQL attributes."""
        metadata = self.fetch_postgres_metadata()
        return metadata.get("attributes", {})
    
    def get_events(self) -> Dict[str, Any]:
        """Get all PostgreSQL events."""
        metadata = self.fetch_postgres_metadata()
        return metadata.get("events", {})
    
    def get_metric_by_name(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific metric definition by name.
        
        Args:
            metric_name: Name of the metric (e.g., "postgresql.backends")
            
        Returns:
            Metric definition or None if not found
        """
        metrics = self.get_metrics()
        return metrics.get(metric_name)
    
    def get_enabled_metrics(self) -> Dict[str, Any]:
        """Get only the metrics that are enabled by default."""
        metrics = self.get_metrics()
        return {
            name: config 
            for name, config in metrics.items() 
            if config.get("enabled", False)
        }
    
    def get_metrics_summary(self) -> Dict[str, Dict[str, str]]:
        """
        Get a summary of all metrics with key information.
        
        Returns:
            Dictionary mapping metric names to {data_type, description}
        """
        metrics = self.get_metrics()
        summary = {}
        
        for name, config in metrics.items():
            # Determine metric type (sum, gauge, histogram, etc.)
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
    
    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self) -> "OTelMetadataFetcher":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


# Convenience function for quick access
def get_postgres_metrics(ref: str = "main") -> Dict[str, Any]:
    """
    Convenience function to quickly fetch PostgreSQL metrics.
    
    Args:
        ref: Git reference to fetch from - branch name (e.g., 'main'), 
             commit SHA, or tag (defaults to 'main' for latest)
        
    Returns:
        Dictionary of PostgreSQL metrics
    """
    with OTelMetadataFetcher(ref) as fetcher:
        return fetcher.get_metrics()

