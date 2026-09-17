class PortQueueError(Exception):
    """Base class for all port-queue errors."""


class MissingColumnError(PortQueueError):
    """A required column could not be found or mapped."""


class InvalidDataError(PortQueueError):
    """A row or value failed validation."""


class InsufficientDataError(PortQueueError):
    """Not enough usable history to measure the port."""


class SaturatedPortError(PortQueueError):
    """Arrivals meet or exceed capacity: the queue can never clear."""
