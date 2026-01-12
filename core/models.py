from dataclasses import dataclass
from core.enums import Role, ApplicationStatus
from core.enums import BranchStatus


@dataclass
class User:
    id: int
    name: str
    role: Role


@dataclass
class InsuranceApplication:
    id: int
    client_name: str
    status: ApplicationStatus = ApplicationStatus.CREATED


@dataclass
class InsuranceContract:
    id: int
    application_id: int
    status: str
    client_signed: int
    director_signed: int
    archived: int
    created_at: str
    updated_at: str

@dataclass
class Branch:
    id: int
    branch_name: str
    status: BranchStatus = BranchStatus.PENDING
    confirmed_by_director: int = 1
    approved_by_lawyer: int = 0
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
