class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str = "", status_code: int = 500, detail: str | None = None):
        self.message = detail if detail is not None else message
        self.detail = self.message
        self.status_code = status_code
        super().__init__(self.message)


class ResourceNotFoundException(AppException):
    """Raised when a requested resource is not found."""

    pass


class UserAlreadyExistsException(AppException):
    """Raised when attempting to register an email that already exists."""

    pass


class InvalidCredentialsException(AppException):
    """Raised when password verification or email matching fails."""

    pass


class AuthenticationException(AppException):
    """Raised when authentication credentials are invalid or missing."""

    pass


class AuthorizationException(AppException):
    """Raised when a user attempts to perform an action they don't have roles/permissions for."""

    pass


class BadRequestException(AppException):
    """Raised when a request is invalid or cannot be processed due to business rules."""

    def __init__(self, message: str = "", detail: str | None = None):
        super().__init__(message=message, status_code=400, detail=detail)


class SupervisorDeactivationConflictException(AppException):
    """Raised when deactivating a supervisor with unresolved active direct reports (HTTP 409)."""

    def __init__(
        self,
        message: str = "Cannot deactivate user with active direct reports. Please reassign subordinates.",
        unresolved_subordinates: list[dict] | None = None,
    ):
        super().__init__(message=message, status_code=409, detail=message)
        self.unresolved_subordinates = unresolved_subordinates or []
