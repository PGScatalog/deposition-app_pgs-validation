from enum import Enum

SUBMISSION_COLLECTION = "PGSSubmission"
SCORINGFILE_COLLECTION = "ScoringFileManagement"

class ValidationStatus(Enum):

    NONE = None
    AWAITING_VALIDATION = "AWAITING_VALIDATION"
    PROCESSING = "PROCESSING"
    VALID = "VALID"
    INVALID = "INVALID"
    ERROR = "ERROR"
