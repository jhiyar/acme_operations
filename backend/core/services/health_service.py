class HealthService:
    """Example service — domain logic lives here, not in views."""

    def call(self) -> dict:
        return {
            "status": "ok",
            "service": "acme-operations",
        }
