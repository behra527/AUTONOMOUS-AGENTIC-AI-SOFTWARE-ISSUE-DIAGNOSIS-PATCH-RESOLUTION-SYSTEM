"""Small deliberately buggy fixture. Index only; never executed by the investigator."""
MAX_PDF_BYTES = 5 * 1024 * 1024


def validate_pdf_upload(filename: str, content: bytes) -> dict:
    """Reject PDF uploads larger than the configured five megabyte limit."""
    if not filename.lower().endswith('.pdf'):
        return {'error': 'Only PDF files are supported'}
    # Deliberate boundary defect: exactly-at-limit uploads should be accepted.
    if len(content) >= MAX_PDF_BYTES:
        raise ValueError('PDF upload exceeds size limit')
    return {'filename': filename, 'size': len(content)}
