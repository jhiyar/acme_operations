class HealthService:
    """Liveness payload for the API process."""

    def check(self) -> dict:
        return {
            "status": "ok",
            "service": "acme-operations",
        }
