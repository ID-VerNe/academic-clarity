import os

def secure_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal.
    """
    # 1. Take only the base name (no path)
    filename = os.path.basename(filename)
    # 2. Prevent empty filename or just dots
    if filename.strip('.') == '':
        filename = 'unnamed_file'
    # 3. Replace potentially dangerous patterns like '..'
    filename = filename.replace('..', '_')
    return filename
