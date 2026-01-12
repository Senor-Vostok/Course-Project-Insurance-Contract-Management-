from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QPushButton, QMessageBox, QListWidget, QGroupBox, QHBoxLayout,
    QSpacerItem, QSizePolicy, QSlider, QTextEdit, QLineEdit, QComboBox
)
from PyQt5.QtCore import Qt

from core.services import InsuranceService
from core.actions import Action
from core.workflow import ALLOWED_ACTIONS
from core.permissions import ACTION_ROLES
from core.enums import ApplicationStatus, Role
from core.storage import storage
from core import db


def _status_pretty(status_name: str) -> str:
    try:
        return ApplicationStatus[status_name].value
    except Exception:
        return status_name


class ApplicationWindow(QWidget):
    def __init__(self, application_id: int, user, parent):
        super().__init__()
        self.application_id = application_id
        self.user = user
        self.parent = parent
        self.service = InsuranceService()

        self.setWindowTitle(f"Заявка #{application_id}")
        self.resize(920, 720)

        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.title = QLabel(f"Заявка #{application_id}")
        self.title.setObjectName("Title")

        self.badge = QLabel(f"{user.role.value}")
        self.badge.setObjectName("Badge")

        header.addWidget(self.title)
        header.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        header.addWidget(self.badge)
        root.addLayout(header)

        info_box = QGroupBox("Информация по заявке")
        info_l = QVBoxLayout()
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        info_l.addWidget(self.info_label)
        info_box.setLayout(info_l)
        root.addWidget(info_box)

        self.role_box = QGroupBox("Действия")
        self.role_l = QVBoxLayout()
        self.role_l.setSpacing(10)
        self.role_box.setLayout(self.role_l)
        root.addWidget(self.role_box)

        self.contract_box = QGroupBox("Договор")
        contract_l = QVBoxLayout()
        self.contract_label = QLabel()
        self.contract_label.setWordWrap(True)
        contract_l.addWidget(self.contract_label)

        self.contract_draft = QTextEdit()
        self.contract_draft.setPlaceholderText("Текст проекта договора (черновик)")
        contract_l.addWidget(self.contract_draft)

        self.contract_box.setLayout(contract_l)
        root.addWidget(self.contract_box)

        logs_box = QGroupBox("Лог (в памяти)")
        logs_l = QVBoxLayout()
        self.log_list = QListWidget()
        logs_l.addWidget(self.log_list)
        logs_box.setLayout(logs_l)
        root.addWidget(logs_box, 1)

        self.setLayout(root)
        self.update_ui()

    def _allowed_for_user(self, status: ApplicationStatus, action: Action) -> bool:
        allowed = ALLOWED_ACTIONS.get(status, set())
        return (action in allowed) and (self.user.role in ACTION_ROLES.get(action, set()))

    def _clear_role_layout(self):
        while self.role_l.count():
            item = self.role_l.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _run(self, action: Action, data=None):
        try:
            self.service.perform_action(self.application_id, action, self.user, data=data or {})
            self.update_ui()
            self.parent.refresh_current_list()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    # ---- role UIs ----

    def _build_client_ui(self, status: ApplicationStatus):
        if self._allowed_for_user(status, Action.CLIENT_SIGN):
            btn = QPushButton("Подписать договор")
            btn.clicked.connect(lambda: self._run(Action.CLIENT_SIGN))
            self.role_l.addWidget(btn)
        else:
            self.role_l.addWidget(QLabel("Нет действий по этой заявке на текущем этапе."))

    def _build_underwriter_ui(self, status: ApplicationStatus):
        if not self._allowed_for_user(status, Action.ASSESS_RISK):
            self.role_l.addWidget(QLabel("Нет действий по этой заявке на текущем этапе."))
            return

        box = QGroupBox("Оценка риска и выбор вида страхования")
        l = QVBoxLayout()
        l.setSpacing(8)

        self.risk_slider = QSlider(Qt.Horizontal)
        self.risk_slider.setMinimum(0)
        self.risk_slider.setMaximum(100)
        self.risk_slider.setValue(0)

        self.risk_value = QLabel("Риск: 0%")
        self.risk_value.setObjectName("Muted")
        self.risk_slider.valueChanged.connect(lambda v: self.risk_value.setText(f"Риск: {v}%"))

        l.addWidget(self.risk_value)
        l.addWidget(self.risk_slider)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Выберите вид страхования...", None)
        for t in db.list_insurance_types(active_only=True):
            self.type_combo.addItem(t["name"], int(t["id"]))

        l.addWidget(QLabel("Вид страхования (из БД):"))
        l.addWidget(self.type_combo)

        submit = QPushButton("Сохранить и отправить администратору")
        submit.clicked.connect(self._submit_underwriter)
        l.addWidget(submit)

        box.setLayout(l)
        self.role_l.addWidget(box)

    def _submit_underwriter(self):
        risk = int(self.risk_slider.value())
        type_id = self.type_combo.currentData()
        if type_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите вид страхования.")
            return
        self._run(Action.ASSESS_RISK, data={"risk_percent": risk, "insurance_type_id": int(type_id)})

    def _build_admin_ui(self, status: ApplicationStatus):
        if not (self._allowed_for_user(status, Action.APPROVE) or self._allowed_for_user(status, Action.REJECT)):
            self.role_l.addWidget(QLabel("Нет действий по этой заявке на текущем этапе."))
            return

        box = QGroupBox("Решение администратора")
        l = QVBoxLayout()
        l.setSpacing(8)

        self.sum_input = QLineEdit()
        self.sum_input.setPlaceholderText("Страховая сумма (например: 500000)")

        self.rate_input = QLineEdit()
        self.rate_input.setPlaceholderText("Тарифная ставка % (например: 2.5)")

        approve = QPushButton("Одобрить")
        approve.clicked.connect(self._approve_with_sum_rate)

        reject = QPushButton("Отклонить")
        reject.setObjectName("Secondary")
        reject.clicked.connect(lambda: self._run(Action.REJECT))

        l.addWidget(QLabel("При одобрении укажите страховую сумму и тарифную ставку:"))
        l.addWidget(self.sum_input)
        l.addWidget(self.rate_input)

        row = QHBoxLayout()
        row.addWidget(approve)
        row.addWidget(reject)
        l.addLayout(row)

        box.setLayout(l)
        self.role_l.addWidget(box)

    def _approve_with_sum_rate(self):
        s = self.sum_input.text().strip().replace(",", ".")
        r = self.rate_input.text().strip().replace(",", ".")
        self._run(Action.APPROVE, data={"insurance_sum": s, "tariff_rate": r})

    def _build_lawyer_ui(self, status: ApplicationStatus):
        if self._allowed_for_user(status, Action.PREPARE_CONTRACT):
            box = QGroupBox("Подготовка договора")
            l = QVBoxLayout()
            l.setSpacing(8)

            branches = db.list_approved_branches()
            self.branch_combo = QComboBox()
            self.branch_combo.addItem("Выберите филиал...", None)
            for b in branches:
                label = f"{b['branch_name']} — {b.get('address','')} — {b.get('phone','')}"
                self.branch_combo.addItem(label, int(b["id"]))

            l.addWidget(QLabel("Филиал, в котором заключался договор:"))
            l.addWidget(self.branch_combo)

            l.addWidget(QLabel("Проект договора:"))
            self.draft_edit = QTextEdit()
            self.draft_edit.setPlaceholderText("Введите текст проекта договора...")
            l.addWidget(self.draft_edit, 1)

            btn = QPushButton("Создать проект договора")
            btn.clicked.connect(self._prepare_contract)
            l.addWidget(btn)

            box.setLayout(l)
            self.role_l.addWidget(box)
            return

        if self._allowed_for_user(status, Action.ARCHIVE_CONTRACT):
            box = QGroupBox("Архивация")
            l = QVBoxLayout()
            l.addWidget(QLabel("Все подписи получены. Можно архивировать договор."))
            btn = QPushButton("Заархивировать")
            btn.clicked.connect(lambda: self._run(Action.ARCHIVE_CONTRACT))
            l.addWidget(btn)
            box.setLayout(l)
            self.role_l.addWidget(box)
            return

        self.role_l.addWidget(QLabel("Нет действий по этой заявке на текущем этапе."))

    def _prepare_contract(self):
        branch_id = self.branch_combo.currentData()
        if branch_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите филиал.")
            return
        draft = self.draft_edit.toPlainText().strip()
        self._run(Action.PREPARE_CONTRACT, data={"branch_id": int(branch_id), "draft_text": draft})

    def _build_director_ui(self, status: ApplicationStatus):
        if self._allowed_for_user(status, Action.DIRECTOR_SIGN):
            btn = QPushButton("Подписать договор (директор филиала)")
            btn.clicked.connect(lambda: self._run(Action.DIRECTOR_SIGN))
            self.role_l.addWidget(btn)
        else:
            self.role_l.addWidget(QLabel("Нет действий по этой заявке на текущем этапе."))

    def update_ui(self):
        app = db.get_application(self.application_id)
        if not app:
            self.info_label.setText("Заявка удалена или не найдена.")
            self.role_box.setVisible(False)
            self.contract_box.setVisible(False)
            return

        status = ApplicationStatus[app["status"]]
        status_pretty = _status_pretty(app["status"])

        # вид страхования (1)
        type_name = "—"
        if app.get("insurance_type_id") is not None:
            t = db.get_insurance_type(int(app["insurance_type_id"]))
            if t:
                type_name = t["name"]

        insurance_sum = app.get("insurance_sum")
        tariff_rate = app.get("tariff_rate")
        tariff_amount = app.get("tariff_amount")

        self.info_label.setText(
            f"ФИО клиента: {app.get('client_fio', '')}\n"
            f"Объект: {app.get('insured_object', '')}\n"
            f"Описание: {app.get('request_text', '')}\n\n"
            f"Статус: {status_pretty}\n"
            f"Риск: {int(app.get('risk_percent') or 0)}%\n"
            f"Вид страхования: {type_name}\n"
            f"Страховая сумма: {insurance_sum if insurance_sum is not None else '—'}\n"
            f"Тарифная ставка (%): {tariff_rate if tariff_rate is not None else '—'}\n"
            f"Тариф к оплате: {tariff_amount if tariff_amount is not None else '—'}\n"
            f"updated_at: {app.get('updated_at')}"
        )

        contract = db.get_contract_by_application(self.application_id)
        show_contract = bool(contract) or (self.user.role == Role.LAWYER and status == ApplicationStatus.APPROVED)
        self.contract_box.setVisible(show_contract)

        if not show_contract:
            self.contract_label.setText("")
            self.contract_draft.setVisible(False)
        else:
            if not contract:
                self.contract_label.setText("Договор ещё не создан.")
                self.contract_draft.setVisible(False)
            else:
                branch_name = "—"
                if contract.get("branch_id"):
                    b = db.get_branch(int(contract["branch_id"]))
                    if b:
                        branch_name = f"{b.get('branch_name','')} ({b.get('address','')}, {b.get('phone','')})"

                c_type = "—"
                if contract.get("insurance_type_id") is not None:
                    t = db.get_insurance_type(int(contract["insurance_type_id"]))
                    if t:
                        c_type = t["name"]

                self.contract_label.setText(
                    f"Дата заключения: {contract.get('contract_date','—')}\n"
                    f"Филиал: {branch_name}\n"
                    f"Вид страхования: {c_type}\n"
                    f"Страховая сумма: {contract.get('insurance_sum','—')}\n"
                    f"Тарифная ставка (%): {contract.get('tariff_rate','—')}\n"
                    f"Тариф к оплате: {contract.get('tariff_amount','—')}\n\n"
                    f"Подписано клиентом: {bool(contract.get('client_signed'))}\n"
                    f"Подписано директором: {bool(contract.get('director_signed'))}\n"
                    f"Архивировано: {bool(contract.get('archived'))}\n"
                    f"updated_at: {contract.get('updated_at')}"
                )

                if self.user.role == Role.LAWYER:
                    self.contract_draft.setVisible(True)
                    self.contract_draft.setPlainText(contract.get("draft_text") or "")
                    self.contract_draft.setReadOnly(True)
                else:
                    self.contract_draft.setVisible(False)

        self._clear_role_layout()
        if self.user.role == Role.CLIENT:
            self._build_client_ui(status)
        elif self.user.role == Role.UNDERWRITER:
            self._build_underwriter_ui(status)
        elif self.user.role == Role.ADMIN:
            self._build_admin_ui(status)
        elif self.user.role == Role.LAWYER:
            self._build_lawyer_ui(status)
        elif self.user.role == Role.BRANCH_DIRECTOR:
            self._build_director_ui(status)
        else:
            self.role_l.addWidget(QLabel("Роль не поддерживается."))

        self.log_list.clear()
        self.log_list.addItems(storage.logs)
