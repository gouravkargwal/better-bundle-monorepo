
class DataStorageError(Exception):
    """Raised when data storage operations fail"""
    def __init__(self, message: str, operation: str = "unknown", data_type: str = "unknown"):
        self.message = message
        self.operation = operation
        self.data_type = data_type
        super().__init__(self.message)

