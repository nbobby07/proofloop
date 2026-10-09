"""Safe, stable provider failures; never include upstream bodies or credentials."""


class ProviderError(RuntimeError):
    def __init__(self, provider: str, code: str, *, retryable: bool = False):
        self.provider = provider
        self.code = code
        self.retryable = retryable
        super().__init__(f"{provider}: {code}")
