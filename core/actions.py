from enum import Enum


class Action(Enum):
    ASSESS_RISK = "Оценить риск"
    APPROVE = "Одобрить"
    REJECT = "Отклонить"
    PREPARE_CONTRACT = "Подготовить договор"

    CLIENT_SIGN = "Подписать (клиент)"
    DIRECTOR_SIGN = "Подписать (директор)"

    ARCHIVE_CONTRACT = "Заархивировать договор (в БД)"
