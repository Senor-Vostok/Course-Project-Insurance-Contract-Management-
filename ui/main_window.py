from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QComboBox, QMessageBox, QGroupBox,
    QLineEdit, QTextEdit, QStackedWidget
)

from core.models import User
from core.enums import Role, ApplicationStatus, BranchStatus
from core.storage import storage
from core.workflow import ALLOWED_ACTIONS
from core.permissions import ACTION_ROLES
from core import db
from ui.application_window import ApplicationWindow
from ui.branch_window import BranchWindow


def _app_status_pretty(status_name: str) -> str:
    try:
        return ApplicationStatus[status_name].value
    except Exception:
        return status_name


def _branch_status_pretty(status_name: str) -> str:
    try:
        return BranchStatus[status_name].value
    except Exception:
        return status_name


def _needs_user_action(app_row: dict, user: User) -> bool:
    """Показываем только то, где пользователь реально может выполнить действие сейчас."""
    try:
        status = ApplicationStatus[app_row["status"]]
    except Exception:
        return False

    allowed_actions = ALLOWED_ACTIONS.get(status, set())
    for a in allowed_actions:
        if user.role in ACTION_ROLES.get(a, set()):
            if user.role == Role.CLIENT and app_row.get("client_name") != user.name:
                return False
            return True
    return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Черновик на базе BPMN")
        self.resize(980, 640)

        self._init_users()
        self._init_ui()
        self.refresh_current_list()

    def _init_users(self):
        if not storage.users:
            storage.users = [
                User(1, "User", Role.CLIENT),
                User(2, "User", Role.UNDERWRITER),
                User(3, "User", Role.ADMIN),
                User(4, "User", Role.LAWYER),
                User(5, "User", Role.BRANCH_DIRECTOR),
            ]

    def _init_ui(self):
        central = QWidget()
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Черновик на базе BPMN")
        title.setObjectName("Title")
        root.addWidget(title)

        # Контекст
        ctx = QGroupBox("Контекст")
        ctx_l = QHBoxLayout()

        self.user_combo = QComboBox()
        for user in storage.users:
            self.user_combo.addItem(f"{user.name} ({user.role.value})", user)
        self.user_combo.currentIndexChanged.connect(self.on_context_changed)

        self.section_combo = QComboBox()
        self.section_combo.currentIndexChanged.connect(lambda _: self.refresh_current_list())

        ctx_l.addWidget(QLabel("Пользователь:"))
        ctx_l.addWidget(self.user_combo, 1)
        ctx_l.addWidget(QLabel("Раздел:"))
        ctx_l.addWidget(self.section_combo)
        ctx.setLayout(ctx_l)
        root.addWidget(ctx)

        # Создание (stacked)
        create_box = QGroupBox("Создание")
        create_l = QVBoxLayout()
        create_l.setSpacing(8)

        self.create_stack = QStackedWidget()

        # 0) пусто
        empty = QWidget()
        self.create_stack.addWidget(empty)

        # 1) Клиент: создать страховую заявку
        self.client_create = QWidget()
        cl = QVBoxLayout()
        cl.setSpacing(8)

        self.client_fio = QLineEdit()
        self.client_fio.setPlaceholderText("ФИО (например: Иванов Иван Иванович)")

        self.client_object = QLineEdit()
        self.client_object.setPlaceholderText("Объект страхования (например: квартира, авто, склад...)")

        self.client_text = QTextEdit()
        self.client_text.setPlaceholderText("Текстовая справка: что хотите застраховать и от каких рисков...")

        self.client_create_btn = QPushButton("Создать заявку")
        self.client_create_btn.clicked.connect(self.create_application_from_client)

        cl.addWidget(self.client_fio)
        cl.addWidget(self.client_object)
        cl.addWidget(self.client_text, 1)
        cl.addWidget(self.client_create_btn)

        self.client_create.setLayout(cl)
        self.create_stack.addWidget(self.client_create)

        # 2) Директор: создать филиал
        self.branch_create = QWidget()
        bl = QVBoxLayout()
        bl.setSpacing(8)

        self.branch_name = QLineEdit()
        self.branch_name.setPlaceholderText("Название филиала (юридически зарегистрированный)")

        self.branch_create_btn = QPushButton("Создать заявку на филиал")
        self.branch_create_btn.clicked.connect(self.create_branch_from_director)

        bl.addWidget(self.branch_name)
        bl.addWidget(self.branch_create_btn)

        self.branch_create.setLayout(bl)
        self.create_stack.addWidget(self.branch_create)

        create_l.addWidget(self.create_stack)
        create_box.setLayout(create_l)
        root.addWidget(create_box, 1)

        # Список
        list_box = QGroupBox("Мои задачи")
        list_l = QVBoxLayout()

        self.list_widget = QListWidget()
        list_l.addWidget(self.list_widget, 1)

        row = QHBoxLayout()
        self.open_btn = QPushButton("Открыть")
        self.open_btn.clicked.connect(self.open_item)

        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.setObjectName("Secondary")
        self.refresh_btn.clicked.connect(self.refresh_current_list)

        row.addWidget(self.open_btn)
        row.addWidget(self.refresh_btn)
        row.addStretch(1)
        list_l.addLayout(row)

        self.hint = QLabel("")
        self.hint.setObjectName("Muted")
        list_l.addWidget(self.hint)

        list_box.setLayout(list_l)
        root.addWidget(list_box, 2)

        central.setLayout(root)
        self.setCentralWidget(central)

        self.on_context_changed()

    def current_user(self) -> User:
        return self.user_combo.currentData()

    def current_section(self) -> str:
        return str(self.section_combo.currentData() or "applications")

    def on_context_changed(self):
        self._rebuild_sections_for_role()
        self._rebuild_create_panel_for_role()
        self.refresh_current_list()

    def _rebuild_sections_for_role(self):
        user = self.current_user()
        self.section_combo.blockSignals(True)
        self.section_combo.clear()

        self.section_combo.addItem("Страховые заявки", "applications")

        if user and user.role in {Role.BRANCH_DIRECTOR, Role.LAWYER}:
            self.section_combo.addItem("Регистрация филиалов", "branches")

        self.section_combo.blockSignals(False)

    def _rebuild_create_panel_for_role(self):
        user = self.current_user()
        section = self.current_section()

        if not user:
            self.create_stack.setCurrentIndex(0)
            return

        if section == "applications":
            if user.role == Role.CLIENT:
                self.create_stack.setCurrentWidget(self.client_create)
            else:
                self.create_stack.setCurrentIndex(0)

        elif section == "branches":
            if user.role == Role.BRANCH_DIRECTOR:
                self.create_stack.setCurrentWidget(self.branch_create)
            else:
                self.create_stack.setCurrentIndex(0)

    def refresh_current_list(self):
        self._rebuild_create_panel_for_role()
        self.list_widget.clear()

        user = self.current_user()
        if not user:
            return

        section = self.current_section()

        if section == "branches":
            branches = db.list_branches()

            filtered = []
            if user.role == Role.LAWYER:
                for b in branches:
                    if b["status"] == BranchStatus.PENDING.name and int(b["approved_by_lawyer"]) == 0:
                        filtered.append(b)
            elif user.role == Role.BRANCH_DIRECTOR:
                for b in branches:
                    if b.get("created_by") == user.name:
                        filtered.append(b)
            else:
                filtered = []

            for b in filtered:
                st = _branch_status_pretty(b["status"])
                self.list_widget.addItem(f"Филиал #{b['id']}  •  {st}  •  {b['branch_name']}")
            self.hint.setText(f"Филиалов в работе: {len(filtered)}")
            return

        apps = db.list_applications()
        actionable = [a for a in apps if _needs_user_action(a, user)]

        for a in actionable:
            st = _app_status_pretty(a["status"])
            fio = a.get("client_fio", "")
            obj = a.get("insured_object", "")
            self.list_widget.addItem(f"Заявка #{a['id']}  •  {st}  •  {fio}  •  {obj}")
        self.hint.setText(f"Заявок, требующих вашего действия: {len(actionable)}")

    def create_application_from_client(self):
        user = self.current_user()
        if not user or user.role != Role.CLIENT:
            return

        fio = self.client_fio.text().strip()
        obj = self.client_object.text().strip()
        txt = self.client_text.toPlainText().strip()

        try:
            if not fio:
                raise ValueError("Укажи ФИО.")
            if not obj:
                raise ValueError("Укажи объект страхования.")
            if len(txt) < 10:
                raise ValueError("Добавь описание (минимум 10 символов).")

            new_id = db.create_application(user.name, client_fio=fio, insured_object=obj, request_text=txt)
            storage.log(f"Клиент '{user.name}' создал заявку #{new_id}")
            self.client_object.clear()
            self.client_fio.clear()
            self.client_text.clear()
            self.refresh_current_list()

        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def create_branch_from_director(self):
        user = self.current_user()
        if not user or user.role != Role.BRANCH_DIRECTOR:
            return

        name = self.branch_name.text().strip()
        try:
            if not name:
                raise ValueError("Укажи название филиала.")
            new_id = db.create_branch_request(name, created_by=user.name)
            storage.log(f"Директор '{user.name}' создал заявку на филиал #{new_id} ({name})")
            self.branch_name.clear()
            self.refresh_current_list()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def open_item(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return

        user = self.current_user()
        if not user:
            return

        section = self.current_section()

        try:
            if section == "branches":
                all_branches = db.list_branches()
                if user.role == Role.LAWYER:
                    filtered = [b for b in all_branches if
                                b["status"] == BranchStatus.PENDING.name and int(b["approved_by_lawyer"]) == 0]
                elif user.role == Role.BRANCH_DIRECTOR:
                    filtered = [b for b in all_branches if b.get("created_by") == user.name]
                else:
                    filtered = []

                if row >= len(filtered):
                    return
                branch_id = filtered[row]["id"]
                self.branch_window = BranchWindow(branch_id, user, self)
                self.branch_window.show()
                return

            all_apps = db.list_applications()
            actionable = [a for a in all_apps if _needs_user_action(a, user)]
            if row >= len(actionable):
                return
            app_id = actionable[row]["id"]
            self.app_window = ApplicationWindow(app_id, user, self)
            self.app_window.show()

        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))
