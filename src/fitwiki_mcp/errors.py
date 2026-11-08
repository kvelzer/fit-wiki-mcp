"""Stable, secret-free errors at the service boundary."""


class WikiError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(f"{code}: {message}")

    def result(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "retryable": self.retryable}}
