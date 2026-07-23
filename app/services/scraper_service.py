from app.services.zmr_inges import IngestionSummary, run_zoommer_ingestion


async def refresh_full_catalog() -> IngestionSummary:
    """Refresh the catalog behind a worker-friendly service boundary."""
    return await run_zoommer_ingestion()
