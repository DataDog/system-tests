"""
Standalone FastAPI service for fetching OpenTelemetry PostgreSQL receiver metadata.
No Rapid dependencies required - runs anywhere!
"""
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from otel_metadata_fetcher import OTelMetadataFetcher


# Initialize the OTel metadata fetcher
fetcher = OTelMetadataFetcher()

# Create FastAPI app
app = FastAPI(
    title="OTel PostgreSQL Metadata Service",
    description="Fetch and query OpenTelemetry PostgreSQL receiver metadata from GitHub",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Request models
class MetricRequest(BaseModel):
    """Request model for metric queries."""
    commit_sha: Optional[str] = Field(None, description="Optional specific commit SHA to fetch from")


class MetricByNameRequest(BaseModel):
    """Request model for getting a specific metric."""
    metric_name: str = Field(..., description="Name of the metric (e.g., 'postgresql.backends')")
    commit_sha: Optional[str] = Field(None, description="Optional specific commit SHA to fetch from")


# Helper function to handle ref override
def get_fetcher(ref: Optional[str]) -> OTelMetadataFetcher:
    """Get appropriate fetcher based on git ref (branch, commit SHA, or tag)."""
    if ref:
        return OTelMetadataFetcher(ref)
    return fetcher


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint with service information."""
    return {
        "service": "OTel PostgreSQL Metadata Service",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": "/api/v1/*",
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/v1/metrics")
async def get_all_metrics(
    commit_sha: Optional[str] = Query(None, description="Optional git ref: branch name (e.g., 'main'), commit SHA, or tag")
) -> Dict[str, Any]:
    """
    Get all PostgreSQL receiver metrics from OpenTelemetry Collector Contrib.
    
    Defaults to latest from 'main' branch. You can specify a different branch, commit SHA, or tag.
    
    **Example:**
    - GET /api/v1/metrics (uses latest from main)
    - GET /api/v1/metrics?commit_sha=main (explicit main branch)
    - GET /api/v1/metrics?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c (specific commit)
    - GET /api/v1/metrics?commit_sha=v0.91.0 (specific tag)
    """
    try:
        temp_fetcher = get_fetcher(commit_sha)
        try:
            return temp_fetcher.get_metrics()
        finally:
            if commit_sha:
                temp_fetcher.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metrics: {str(e)}")


@app.get("/api/v1/metrics/enabled")
async def get_enabled_metrics(
    commit_sha: Optional[str] = Query(None, description="Optional specific commit SHA to fetch from")
) -> Dict[str, Any]:
    """
    Get only the enabled PostgreSQL receiver metrics.
    
    **Example:**
    - GET /api/v1/metrics/enabled
    - GET /api/v1/metrics/enabled?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c
    """
    try:
        temp_fetcher = get_fetcher(commit_sha)
        try:
            return temp_fetcher.get_enabled_metrics()
        finally:
            if commit_sha:
                temp_fetcher.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch enabled metrics: {str(e)}")


@app.get("/api/v1/metrics/summary")
async def get_metrics_summary(
    commit_sha: Optional[str] = Query(None, description="Optional git ref: branch name (e.g., 'main'), commit SHA, or tag"),
    enabled_only: bool = Query(False, description="Return only enabled metrics")
) -> Dict[str, Dict[str, str]]:
    """
    Get a summary of all PostgreSQL metrics with key information.
    
    Returns: Dictionary mapping metric names to {data_type, description}.
    Defaults to latest from 'main' branch.
    
    **Example:**
    - GET /api/v1/metrics/summary (uses latest from main)
    - GET /api/v1/metrics/summary?enabled_only=true
    - GET /api/v1/metrics/summary?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c
    
    **Output format:**
    ```json
    {
      "postgresql.backends": {
        "data_type": "Sum",
        "description": "The number of backends."
      }
    }
    ```
    """
    try:
        temp_fetcher = get_fetcher(commit_sha)
        try:
            if enabled_only:
                # Get full metrics data to filter by enabled status
                all_metrics = temp_fetcher.get_metrics()
                enabled_metrics = {name: config for name, config in all_metrics.items() if config.get("enabled", False)}
                
                # Build summary for enabled metrics only
                summary = {}
                for name, config in enabled_metrics.items():
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
            else:
                return temp_fetcher.get_metrics_summary()
        finally:
            if commit_sha:
                temp_fetcher.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metrics summary: {str(e)}")


@app.get("/api/v1/metrics/{metric_name}")
async def get_metric_by_name(
    metric_name: str,
    commit_sha: Optional[str] = Query(None, description="Optional specific commit SHA to fetch from")
) -> Dict[str, Any]:
    """
    Get a specific PostgreSQL metric definition by name.
    
    **Example:**
    - GET /api/v1/metrics/postgresql.backends
    - GET /api/v1/metrics/postgresql.db_size?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c
    """
    try:
        temp_fetcher = get_fetcher(commit_sha)
        try:
            metric = temp_fetcher.get_metric_by_name(metric_name)
            if metric is None:
                raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' not found")
            return metric
        finally:
            if commit_sha:
                temp_fetcher.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metric: {str(e)}")


@app.get("/api/v1/resource-attributes")
async def get_resource_attributes(
    commit_sha: Optional[str] = Query(None, description="Optional specific commit SHA to fetch from")
) -> Dict[str, Any]:
    """
    Get PostgreSQL resource attributes.
    
    **Example:**
    - GET /api/v1/resource-attributes
    - GET /api/v1/resource-attributes?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c
    """
    try:
        temp_fetcher = get_fetcher(commit_sha)
        try:
            return temp_fetcher.get_resource_attributes()
        finally:
            if commit_sha:
                temp_fetcher.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch resource attributes: {str(e)}")


@app.get("/api/v1/attributes")
async def get_attributes(
    commit_sha: Optional[str] = Query(None, description="Optional specific commit SHA to fetch from")
) -> Dict[str, Any]:
    """
    Get PostgreSQL attributes.
    
    **Example:**
    - GET /api/v1/attributes
    - GET /api/v1/attributes?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c
    """
    try:
        temp_fetcher = get_fetcher(commit_sha)
        try:
            return temp_fetcher.get_attributes()
        finally:
            if commit_sha:
                temp_fetcher.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch attributes: {str(e)}")


@app.get("/api/v1/events")
async def get_events(
    commit_sha: Optional[str] = Query(None, description="Optional specific commit SHA to fetch from")
) -> Dict[str, Any]:
    """
    Get PostgreSQL events definitions.
    
    **Example:**
    - GET /api/v1/events
    - GET /api/v1/events?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c
    """
    try:
        temp_fetcher = get_fetcher(commit_sha)
        try:
            return temp_fetcher.get_events()
        finally:
            if commit_sha:
                temp_fetcher.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")


@app.get("/api/v1/metadata/full")
async def get_full_metadata(
    commit_sha: Optional[str] = Query(None, description="Optional specific commit SHA to fetch from")
) -> Dict[str, Any]:
    """
    Get the complete PostgreSQL receiver metadata file.
    
    **Example:**
    - GET /api/v1/metadata/full
    - GET /api/v1/metadata/full?commit_sha=270e3cb8cdfe619322be1af2b49a0901d8188a9c
    """
    try:
        temp_fetcher = get_fetcher(commit_sha)
        try:
            return temp_fetcher.fetch_postgres_metadata()
        finally:
            if commit_sha:
                temp_fetcher.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metadata: {str(e)}")


# Shutdown event to clean up
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up resources on shutdown."""
    fetcher.close()


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    host = "0.0.0.0"
    port = 8080
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}, using default 8080")
    
    print(f"🚀 Starting OTel PostgreSQL Metadata Service on http://{host}:{port}")
    print(f"📚 API Docs: http://{host}:{port}/docs")
    print(f"📖 ReDoc: http://{host}:{port}/redoc")
    
    uvicorn.run(app, host=host, port=port)
