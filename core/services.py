from typing import Optional, Dict, Any

from core.workflow import ALLOWED_ACTIONS
from core.permissions import ACTION_ROLES
from core.enums import ApplicationStatus
from core.actions import Action
from core.storage import storage
from core import db


class InsuranceService:
    def perform_action(self, application_id: int, action: Action, user, data: Optional[Dict[str, Any]] = None):
        app = db.get_application(application_id)
        if not app:
            raise ValueError("Заявка не найдена в БД")

        status = ApplicationStatus[app["status"]]

        allowed = ALLOWED_ACTIONS.get(status, set())
        if action not in allowed:
            raise ValueError("Действие недопустимо на данном этапе")

        if user.role not in ACTION_ROLES.get(action, set()):
            raise PermissionError("Недостаточно прав для выполнения действия")

        data = data or {}

        if action == Action.ASSESS_RISK:
            risk_percent = int(data.get("risk_percent", -1))
            type_ids = data.get("type_ids", [])
            if risk_percent < 0 or risk_percent > 100:
                raise ValueError("Процент риска должен быть в диапазоне 0..100")
            if not isinstance(type_ids, list):
                raise ValueError("type_ids должен быть списком")
            if len(type_ids) == 0:
                raise ValueError("Нужно выбрать хотя бы один вид страхования")

            db.set_underwriter_assessment(application_id, risk_percent=risk_percent, type_ids=type_ids)
            db.set_application_status(application_id, ApplicationStatus.RISK_ANALYSIS)

        elif action == Action.APPROVE:
            tariff = data.get("tariff_amount", None)
            if tariff is None:
                raise ValueError("При одобрении нужно указать сумму тарифа")
            try:
                tariff_val = float(tariff)
            except Exception:
                raise ValueError("Тариф должен быть числом")
            if tariff_val <= 0:
                raise ValueError("Тариф должен быть больше 0")

            db.set_admin_decision(application_id, tariff_amount=tariff_val)
            db.set_application_status(application_id, ApplicationStatus.APPROVED)

        elif action == Action.REJECT:
            db.set_application_status(application_id, ApplicationStatus.REJECTED)

        elif action == Action.PREPARE_CONTRACT:
            branch_id = data.get("branch_id", None)
            if branch_id is None:
                raise ValueError("Нужно выбрать филиал для договора")
            try:
                branch_id_int = int(branch_id)
            except Exception:
                raise ValueError("Некорректный филиал")

            branch = db.get_branch(branch_id_int)
            if not branch or branch["status"] != "APPROVED" or int(branch["approved_by_lawyer"]) != 1:
                raise ValueError("Выбранный филиал не одобрен юристом или не найден")

            draft_text = str(data.get("draft_text", "")).strip()
            if not draft_text:
                draft_text = "Проект договора (черновик)."

            contract = db.get_contract_by_application(application_id)
            if not contract:
                db.create_contract(application_id, branch_id=branch_id_int, draft_text=draft_text)
            else:
                db.set_contract_flags(application_id, branch_id=branch_id_int, draft_text=draft_text, status="prepared")

            db.set_application_status(application_id, ApplicationStatus.CONTRACT_PREPARED)

        elif action == Action.CLIENT_SIGN:
            contract = db.get_contract_by_application(application_id)
            if not contract:
                raise ValueError("Нельзя подписать: договор ещё не создан (юрист должен подготовить)")
            db.set_contract_flags(application_id, client_signed=True, status="client_signed")
            db.set_application_status(application_id, ApplicationStatus.CLIENT_SIGNED)

        elif action == Action.DIRECTOR_SIGN:
            contract = db.get_contract_by_application(application_id)
            if not contract:
                raise ValueError("Нельзя подписать: договор ещё не создан")
            if int(contract["client_signed"]) != 1:
                raise ValueError("Сначала должен подписать клиент")
            db.set_contract_flags(application_id, director_signed=True, status="director_signed")
            db.set_application_status(application_id, ApplicationStatus.DIRECTOR_SIGNED)

        elif action == Action.ARCHIVE_CONTRACT:
            contract = db.get_contract_by_application(application_id)
            if not contract:
                raise ValueError("Нельзя архивировать: договора нет в БД")
            if int(contract["client_signed"]) != 1 or int(contract["director_signed"]) != 1:
                raise ValueError("Нельзя архивировать: нет всех подписей (клиент + директор)")
            db.set_contract_flags(application_id, archived=True, status="archived")
            db.set_application_status(application_id, ApplicationStatus.ARCHIVED)

        storage.log(f"{user.role.value} '{user.name}' -> {action.value} (заявка #{application_id})")
