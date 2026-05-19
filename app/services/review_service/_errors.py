REVIEW_UNDO_WINDOW_MINUTES = 60


class ReviewError(Exception):
    pass


class ReviewFinalizedError(ReviewError):
    pass


class ReviewLockConflictError(ReviewError):
    pass


class ReviewDecisionImmutableError(ReviewError):
    pass


class ReviewUndoWindowExpiredError(ReviewError):
    pass


class ReviewNotFinalizedError(ReviewError):
    pass
