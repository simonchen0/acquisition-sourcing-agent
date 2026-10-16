class ProviderUnavailable(ValueError):
    """A required integration or entitlement is unavailable."""


class TransientProviderError(Exception):
    pass


class ProviderThrottled(TransientProviderError):
    def __init__(self, message, retry_after):
        super().__init__(message)
        self.retry_after = retry_after
