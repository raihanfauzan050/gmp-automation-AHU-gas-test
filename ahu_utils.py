import os
import re


_AHU_NUMBER_PATTERN = (
    r'(?:AHU|공조기)[_:\-|–—−]*'
    r'(?:(?:NO\.?)|번호|#)?[_:\-|–—−]*([1-9]\d*)(?!\d|\.\d)'
)


def ahu_sort_key(value):
    """Sort numeric AHUs first without comparing integers and strings."""
    text = str(value).strip()
    if text.isdigit():
        return 0, int(text)
    return 1, text.casefold()


def extract_ahu_number(value, filename=''):
    """Return the OCR AHU, falling back to an explicit filename AHU."""
    value_text = str(value or '').strip()
    if re.fullmatch(r'\d+', value_text):
        number = int(value_text)
        if number > 0:
            return str(number)

    compact = re.sub(r'\s+', '', value_text)
    match = re.search(_AHU_NUMBER_PATTERN, compact, re.IGNORECASE)
    if match:
        return match.group(1)

    filename_text = re.sub(r'\s+', '', os.path.basename(filename))
    filename_match = re.search(
        _AHU_NUMBER_PATTERN,
        filename_text,
        re.IGNORECASE,
    )
    if filename_match:
        return filename_match.group(1)
    return 'unknown'
