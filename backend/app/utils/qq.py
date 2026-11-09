"""QQ number validation shared by schemas and imports."""
import re

QQ_PATTERN = re.compile(r'[0-9]{5,20}')
QQ_ERROR_MESSAGE = 'QQ 号必须是 5-20 位数字'


def is_valid_qq(value: str) -> bool:
    """ASCII digits only (``str.isdigit`` would also accept full-width digits)."""
    return QQ_PATTERN.fullmatch(value) is not None
