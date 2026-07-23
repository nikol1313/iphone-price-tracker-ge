class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


class RefreshInProgressError(ConflictError):
    pass
