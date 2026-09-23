class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []

    def body(self):
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}
