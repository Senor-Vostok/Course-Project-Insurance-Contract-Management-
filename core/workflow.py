from core.enums import ApplicationStatus
from core.actions import Action

ALLOWED_ACTIONS = {
    ApplicationStatus.CREATED: {
        Action.ASSESS_RISK
    },
    ApplicationStatus.RISK_ANALYSIS: {
        Action.APPROVE,
        Action.REJECT
    },
    ApplicationStatus.APPROVED: {
        Action.PREPARE_CONTRACT
    },
    ApplicationStatus.CONTRACT_PREPARED: {
        Action.CLIENT_SIGN
    },
    ApplicationStatus.CLIENT_SIGNED: {
        Action.DIRECTOR_SIGN
    },
    ApplicationStatus.DIRECTOR_SIGNED: {
        Action.ARCHIVE_CONTRACT
    },
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.ARCHIVED: set(),
}
