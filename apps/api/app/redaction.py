import re


def sanitize_log(content):
    if '\x00' in content or len(content.encode('utf-8')) > 64000:
        raise ValueError('Only small UTF-8 text logs are supported')
    patterns = [
        (r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----', '[REDACTED PRIVATE KEY]'),
        (r'(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+', r'\1[REDACTED]'),
        (r'(?i)((?:api[_-]?key|password|secret|access[_-]?token|token)\s*[:=]\s*)[^\s,;]+', r'\1[REDACTED]'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[REDACTED EMAIL]'),
    ]
    cleaned = content
    for pattern, replacement in patterns:
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned, cleaned != content
