import logging


class RedactingFormatter(logging.Formatter):
    def __init__(self, secret: str | None) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")
        self.secret = secret

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        return text.replace(self.secret, "[REDACTED]") if self.secret else text


def configure_logging(level: str, secret: str | None) -> None:
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    root.setLevel(level.upper())
    for handler in root.handlers:
        handler.setFormatter(RedactingFormatter(secret))
