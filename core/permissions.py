from core.enums import Role
from core.actions import Action

ACTION_ROLES = {
    Action.ASSESS_RISK: {Role.UNDERWRITER},
    Action.APPROVE: {Role.ADMIN},
    Action.REJECT: {Role.ADMIN},
    Action.PREPARE_CONTRACT: {Role.LAWYER},

    Action.CLIENT_SIGN: {Role.CLIENT},
    Action.DIRECTOR_SIGN: {Role.BRANCH_DIRECTOR},

    Action.ARCHIVE_CONTRACT: {Role.LAWYER},
}
