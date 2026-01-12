from core.models import Branch, InsuranceApplication, InsuranceContract


class MemoryStorage:
    def __init__(self):
        self.branches: list[Branch] = []
        self.applications: list[InsuranceApplication] = []
        self.contracts: list[InsuranceContract] = []

    def add_branch(self, branch: Branch):
        self.branches.append(branch)

    def add_application(self, application: InsuranceApplication):
        self.applications.append(application)

    def add_contract(self, contract: InsuranceContract):
        self.contracts.append(contract)
