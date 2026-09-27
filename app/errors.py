"""Domain errors, decoupled from HTTP.

Services raise these; `main.py` maps them to JSON responses. This keeps the
business rules free of any web-framework concerns.
"""


class DomainError(Exception):
    status_code = 400
    detail = "Domain error"

    def __init__(self, detail: str | None = None, **extra):
        super().__init__(detail or self.detail)
        self.detail = detail or self.detail
        self.extra = extra


class NotFoundError(DomainError):
    status_code = 404
    detail = "Not found"


class ValidationError(DomainError):
    status_code = 422
    detail = "Validation failed"


class ConflictError(DomainError):
    status_code = 409
    detail = "Conflict"


class OverCapacityError(ValidationError):
    detail = "Guest count exceeds the table capacity"
