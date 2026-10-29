"""Application errors that transports may translate without exposing storage internals."""


class ConflictError(ValueError):
    """The request conflicts with previously recorded event or session identity."""


class StorageError(RuntimeError):
    """Local persistence is unavailable; no policy decision can safely be issued."""


class DeliveryDeferred(Exception):
    """The sink cannot accept an alert now; release its lease for another attempt."""
