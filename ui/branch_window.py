from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QGroupBox, QHBoxLayout, QSpacerItem, QSizePolicy

from core.enums import Role, BranchStatus
from core import db
from core.storage import storage


def _branch_status_pretty(status_name: str) -> str:
    try:
        return BranchStatus[status_name].value
    except Exception:
        return status_name


class BranchWindow(QWidget):
    def __init__(self, branch_id: int, user, parent):
        super().__init__()
        self.branch_id = branch_id
        self.user = user
        self.parent = parent

        self.setWindowTitle(f"Филиал #{branch_id}")
        self.resize(780, 460)

        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.title = QLabel(f"Регистрация филиала #{branch_id}")
        self.title.setObjectName("Title")

        self.badge = QLabel(f"{user.role.value}")
        self.badge.setObjectName("Badge")

        header.addWidget(self.title)
        header.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        header.addWidget(self.badge)
        root.addLayout(header)

        info_box = QGroupBox("Информация о филиале")
        info_l = QVBoxLayout()
        self.info = QLabel()
        self.info.setWordWrap(True)
        info_l.addWidget(self.info)
        info_box.setLayout(info_l)
        root.addWidget(info_box)

        flags_box = QGroupBox("Статус согласований")
        flags_l = QVBoxLayout()
        self.flags = QLabel()
        self.flags.setWordWrap(True)
        flags_l.addWidget(self.flags)
        flags_box.setLayout(flags_l)
        root.addWidget(flags_box)

        self.approve_btn = QPushButton("Одобрить филиал (Юрист)")
        self.approve_btn.clicked.connect(self.approve)
        root.addWidget(self.approve_btn)

        self.setLayout(root)
        self.update_ui()

    def approve(self):
        try:
            if self.user.role != Role.LAWYER:
                raise PermissionError("Одобрить филиал может только Юрист.")

            branch = db.get_branch(self.branch_id)
            if not branch:
                raise ValueError("Заявка на филиал не найдена")

            if int(branch["approved_by_lawyer"]) == 1:
                raise ValueError("Филиал уже одобрен юристом.")

            db.approve_branch_by_lawyer(self.branch_id)
            storage.log(f"Юрист '{self.user.name}' одобрил филиал #{self.branch_id}")
            self.update_ui()
            self.parent.refresh_current_list()

        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def update_ui(self):
        branch = db.get_branch(self.branch_id)
        if not branch:
            self.info.setText("Заявка на филиал не найдена.")
            self.approve_btn.setVisible(False)
            return

        self.info.setText(
            f"Название: {branch.get('branch_name','')}\n"
            f"Адрес: {branch.get('address','')}\n"
            f"Телефон: {branch.get('phone','')}\n\n"
            f"Статус: {_branch_status_pretty(branch.get('status',''))}\n"
            f"Создатель: {branch.get('created_by','')}\n"
            f"updated_at: {branch.get('updated_at','')}"
        )

        confirmed = bool(branch["confirmed_by_director"])
        approved = bool(branch["approved_by_lawyer"])

        self.flags.setText(
            f"Подтверждено директором: {confirmed}\n"
            f"Одобрено юристом: {approved}"
        )

        self.approve_btn.setVisible(self.user.role == Role.LAWYER and not approved)
