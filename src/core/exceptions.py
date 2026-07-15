class AreccaError(Exception):
    pass


class ConfigError(AreccaError):
    pass


class IngestionError(AreccaError):
    pass


class ExtractionError(AreccaError):
    pass


class ValidationError(AreccaError):
    pass


class ComplianceError(AreccaError):
    pass


class StorageError(AreccaError):
    pass


class RetrievalError(AreccaError):
    pass
