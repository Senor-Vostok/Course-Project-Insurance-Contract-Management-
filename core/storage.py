class MemoryStorage:
    def __init__(self):
        self.users = []
        self.logs = []

    def log(self, text: str):
        self.logs.append(text)


storage = MemoryStorage()
