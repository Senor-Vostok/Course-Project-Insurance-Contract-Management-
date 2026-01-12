from enum import Enum


class Role(Enum):
    CLIENT = "Клиент"
    UNDERWRITER = "Андеррайтер"
    ADMIN = "Администратор"
    LAWYER = "Юрист"
    BRANCH_DIRECTOR = "Директор филиала"


class ApplicationStatus(Enum):
    CREATED = "Создана (ожидает оценки рисков)"
    RISK_ANALYSIS = "Анализ риска (ожидает решения администратора)"
    APPROVED = "Одобрена (ожидает подготовки договора)"
    REJECTED = "Отклонена"
    CONTRACT_PREPARED = "Договор подготовлен (ожидает подписи клиента)"
    CLIENT_SIGNED = "Подписано клиентом (ожидает подписи директора)"
    DIRECTOR_SIGNED = "Подписано директором (ожидает архивации юристом)"
    ARCHIVED = "Архивировано"


class BranchStatus(Enum):
    PENDING = "Ожидает одобрения"
    APPROVED = "Одобрен"
