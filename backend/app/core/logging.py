import logging


class RedactingFormatter(logging.Formatter):
    def __init__(self, secret: str | None, *other_secrets: str | None) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")
        self.secrets = tuple(value for value in (secret, *other_secrets) if value)

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")
        return text


def configure_logging(level: str, secret: str | None, *other_secrets: str | None) -> None:
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    root.setLevel(level.upper())
    for handler in root.handlers:
        handler.setFormatter(RedactingFormatter(secret, *other_secrets))
