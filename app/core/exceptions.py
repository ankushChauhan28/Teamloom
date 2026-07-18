class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str):
        self.message = message
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
    pass
