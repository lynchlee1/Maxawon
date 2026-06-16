import re
__all__ = ['split', 'parse_number', 'parse_date']

def split(text: str) -> list:
    '''
    input: text
    output: list of texts that is splitted by '|'
    '''
    return [part.strip() for part in text.split('|')]

def parse_number(text: str) -> float:
    '''
    input: text in string format. ',' is allowed
    output: number
    '''
    try:
        return float(text.replace(',', ''))
    except Exception:
        return -1.0 # returns float to prevent breaking whole process

def parse_date(text: str) -> str:
    '''
    input: text in string format. 'YYYY-MM-DD', 'YYYY.MM.DD', or 'YYYY년 MM월 DD일' is allowed
    output: date in string format YYYY-MM-DD

    Intentionally does NOT validate via datetime objects so that erroneous but
    published dates (e.g. "2022년 08월 32일") are preserved as-is ("2022-08-32")
    rather than silently discarded.
    '''
    try:
        if re.match(r'^\d{4}\.\d{1,2}\.\d{1,2}$', text):
            parts = text.split('.')
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        if re.match(r'^\d{4}년\s*\d{1,2}월\s*\d{1,2}일$', text):
            parts = re.findall(r'\d+', text)
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', text):
            parts = text.split('-')
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        return "-"
    except:
        return "-"
