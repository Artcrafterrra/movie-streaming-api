class PaymentError(Exception):
    """Base class for payment domain errors."""


class OrderNotFoundError(PaymentError):
    """Raised when the target order cannot be found."""


class OrderOwnershipError(PaymentError):
    """Raised when the order does not belong to the acting user."""


class OrderStatusError(PaymentError):
    """Raised when an action is not allowed due to the order's current status."""


class AmountMismatchError(PaymentError):
    """Raised when the payment amount is invalid or exceeds the remaining balance."""


class DuplicateExternalPaymentError(PaymentError):
    """Raised when the provided external_payment_id already exists in the system."""


class PaymentNotFoundError(PaymentError):
    """Raised when the target payment cannot be found."""
