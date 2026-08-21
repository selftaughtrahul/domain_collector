class BaseCollector:
    """Base class for all collectors."""
    
    name = "base"

    async def collect(self, domain: str, **kwargs) -> dict:
        """
        Collect data for a given domain.
        Must return a dictionary matching the SQLAlchemy model fields for the collector.
        """
        raise NotImplementedError
