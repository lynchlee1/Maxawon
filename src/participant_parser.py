import re
from parsing_utils import parse_number

SUMMARY_LABELS = {"합계", "총계", "계"}
PARTICIPANT_NAME_HEADER = "발행 대상자명"
PARTICIPANT_AMOUNT_HEADER_KEYWORDS = ("권면", "총액", "금액")


def is_summary_row_name(text: str) -> bool:
    normalized = re.sub(r"[\s\-\|:()]+", "", text or "")
    return normalized in SUMMARY_LABELS


def _extract_table_rows(table):
    rows = []
    for tr in table.find_all(['tr', 'TR']):
        cells = tr.find_all(['th', 'TH', 'td', 'TD', 'te', 'TE'])
        if cells:
            rows.append([cell.get_text(strip=True) for cell in cells])
    return rows


def _find_participant_column_indices(rows):
    if not rows:
        return -1, -1
    header_row = rows[0]
    name_idx = -1
    amount_idx = -1
    for i, col in enumerate(header_row):
        if PARTICIPANT_NAME_HEADER in col:
            name_idx = i
        if any(keyword in col for keyword in PARTICIPANT_AMOUNT_HEADER_KEYWORDS):
            amount_idx = i
    return name_idx, amount_idx


def _is_participant_table(table):
    rows = _extract_table_rows(table)
    name_idx, amount_idx = _find_participant_column_indices(rows)
    return name_idx != -1 and amount_idx != -1


def _find_last_participant_table(all_tables):
    for idx in range(len(all_tables) - 1, -1, -1):
        table = all_tables[idx]
        if _is_participant_table(table):
            next_table = all_tables[idx + 1] if idx + 1 < len(all_tables) else None
            return table, next_table
    return None, None


def extract_investor_rows(all_tables):
    participant_table, _ = _find_last_participant_table(all_tables)
    if participant_table is None:
        return []

    rows = _extract_table_rows(participant_table)
    name_idx, amount_idx = _find_participant_column_indices(rows)
    if name_idx == -1 or amount_idx == -1:
        return []

    investor_rows = []
    seen = set()
    min_len = max(name_idx, amount_idx) + 1
    for row in rows[1:]:
        if len(row) < min_len:
            continue
        name = row[name_idx].strip()
        amount = parse_number(row[amount_idx])
        if not name or amount <= 0 or is_summary_row_name(name):
            continue
        dedupe_key = (name, amount)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        investor_rows.append({"name": name, "amount": amount})
    return investor_rows


CORPNAMES = {
    "1": {

    },
    "2": {
        "안다": "안다", "아샘": "아샘", "수성": "수성", "리딩": "리딩", "월넛": "월넛", 
        "이현": "이현", "타임": "타임", "삼성": "삼성", "키움": "키움", "노앤": "노앤",
        "코어": "코어", "한양": "한양", "교보": "교보", "현대": "현대", "람다": "람다",
        "아름": "아름", "컴파": "컴파", "대신": "대신", "킹고": "킹고", "신한": "신한", 
        "흥국": "흥국증권",
        "SP": "SP", "SH": "SH", "NH": "NH", "KY": "KY", "JW": "JW",
    },
    "3": {
        "칸서스": "칸서스", "나이스": "나이스", "포커스": "포커스", "마스터": "마스터",
        "와이씨": "와이씨", "코람코": "코람코", "이지스": "이지스", "시너지": "시너지",
        "라이프": "라이프", "아트만": "아트만", "에이원": "에이원", "레이크": "레이크",
        "문스톤": "문스톤", "크로톤": "크로톤", "프렌드": "프렌드", "파로스": "파로스",
        "라이언": "라이언", "린드먼": "린드먼", "블랙펄": "블랙펄", "에이스": "에이스",
        "유암코": "유암코", "타이거": "타이거", "스마일": "스마일", "디파인": "디파인",
        "가이아": "가이아",
        "GVA": "GVA", 
    },
    "4": {
        "라이노스": "라이노스", "르네상스": "르네상스", "한국밸류": "한국밸류", "오라이언": "오라이언",
        "피보나치": "피보나치", "마일스톤": "마일스톤", "삼성증권": "삼성증권", "아스트라": "아스트라", 
        "이아이피": "이아이피", "썬앤트리": "썬앤트리", "지베스코": "지베스코", "씨스퀘어": "씨스퀘어",
        "인피니티": "인피니티", "코너스톤": "코너스톤", "키움증권": "키움증권", "히스토리": "히스토리",
        "한화투자": "한화증권", "신한자산": "신한자산", "신한투자": "신한증권", "다올투자": "다올증권",
        "셀레니언": "셀레니언", "한국투자": "한국투자", "파라투스": "파라투스", "브라이트": "브라이트",
        "윈베스트": "윈베스트", "파인밸류": "파인밸류", "트러스톤": "트러스톤", "패스웨이": "패스웨이",
        "NH앱솔": "NH헤지", "NH헤지": "NH헤지", "디비증권": "DB증권", "DB증권": "DB증권",
        "NH투자": "NH증권", 
        "KDBC": "KDBC", "IBKC": "IBKC", "디에스씨": "DSC",
    },
    "5": {
        "지브이에이": "GVA", "IBK투자": "IBK증권", "브로드하이": "브로드하이", "코리아에셋": "코리아에셋",
        "알파플러스": "알파플러스", "아이비케이": "IBK", "컴퍼니케이": "컴퍼니케이",
        "케이비증권": "KB증권", "제이씨에셋": "JC에셋",
    },
    "6": {
        "아이트러스트": "아이트러스트","미래에셋증권": "미래에셋증권", "유진투자증권": "유진증권", 
        "엔에이치투자": "NH증권",
        "아이비케이씨": "IBKC", "한국투자증권": "한투증권", "비엔케이증권": "BNK증권",
    },
    "7": {
        "아이비케이투자": "IBK증권", "디에스투자증권": "DS증권",
    },
    "8": {
        "이베스트투자증권": "이베스트증권", "비엔케이투자증권": "BNK증권",
        "아이비케이캐피탈": "IBK캐피탈", "제이비우리캐피탈": "JB우리캐피탈",
    },
    "9": {
        "IPARTNERS": "아이파트너스",
    },
    "10": {
        "HYUNSTEADY": "HYUNSTEADY",
    }
}

def preprocess_fundname(fundname: str) -> str:
    replacements = ["주식회사 ", " 주식회사", "(주)"]
    for replacement in replacements:
        fundname = fundname.replace(replacement, '')
    return fundname

def fundname_to_corpname(fundname: str) -> str:
    corpnames = CORPNAMES
    fundname = fundname.replace(' ','')
    replacements = [' ', '주식회사', '(주)', '㈜']
    for replacement in replacements:
        fundname = fundname.replace(replacement, '')

    is_shingisa = False
    if '신기술' in fundname and '조합' in fundname: is_shingisa = True

    corp_found = ""
    for i in range(len(corpnames), 0, -1): 
        prefix = fundname[:i]
        remaining = fundname[i:]
        for match, corp_name in corpnames[str(i)].items():
            if match == prefix: 
                corp_found = corp_name

        found_names = []
        if corp_found: 
            found_names = [corp_found]
            for i in range(len(corpnames), 0, -1):
                for match, corp_name in corpnames[str(i)].items():
                    if match in remaining: 
                        found_names.append(corp_name)

        if corp_found:
            break

    if found_names:
        corp_found = '-'.join(found_names)
    
    if corp_found and is_shingisa: fundname = corp_found + " 신기사"
    if corp_found and not is_shingisa: fundname = corp_found

    return fundname

def fundname_to_corpname_safe(fundname: str) -> str:
    if "-" in fundname: return preprocess_fundname(fundname)
    else: return fundname_to_corpname(fundname)

def format_final_table_text(final_table):
    parts = []
    for row in final_table:
        corp_name = str(row["발행 대상자명"])
        value = row["권면"] / 10**8
        if value.is_integer():
            value_str = f"{int(value)}"
        else:
            value_str = f"{value:.1f}"
        parts.append(f"{corp_name} {value_str}")
    return ', '.join(parts)

def list_fund_participants(all_tables): 
    first_table, second_table = _find_last_participant_table(all_tables)
    first_table_filtered = []
    second_table_rows = []

    if first_table is not None:
        first_table_rows = []
        thead = first_table.find(['thead', 'THEAD'])
        if thead:
            for tr in thead.find_all(['tr', 'TR']):
                cells = tr.find_all(['th', 'TH'])
                if cells:
                    header_row = [cell.get_text(strip=True) for cell in cells]
                    first_table_rows.append(header_row)
        
        tbody = first_table.find(['tbody', 'TBODY'])
        if tbody:
            for tr in tbody.find_all(['tr', 'TR']):
                all_cells = tr.find_all(['td', 'TD', 'te', 'TE'])
                if all_cells:
                    row = [cell.get_text(strip=True) for cell in all_cells]
                    first_table_rows.append(row)

        if first_table_rows and max(len(row) for row in first_table_rows) >= 2:
            idx_col1 = -1
            idx_col2 = -1
            for i, col in enumerate(first_table_rows[0]):
                if '발행 대상자명' in col: idx_col1 = i
                if '권면' in col or '총액' in col or '금액' in col: idx_col2 = i
            if idx_col1 != -1 and idx_col2 != -1:
                candidate_rows = first_table_rows[1:]
            else:
                candidate_rows = []
            
            def extract_bonken_numbers(text):
                if '(' in text and '본건' in text: # Check if text contains '(' and '본건'
                    # Handle both cases: "corpname+(본건#)" and "(본건#)+corpname"
                    if text.startswith('('):
                        before_paren = text.split(')')[0] if ')' in text else text
                        numbers = re.findall(r'\d+', before_paren) # find all numbers
                    else:
                        after_paren = text.split('(')[1] if '(' in text else text
                        numbers = re.findall(r'\d+', after_paren) # find all numbers
                    
                    if numbers: return '|'.join(numbers) # Join numbers with '|' separator
                return text  

            for row in candidate_rows:
                if len(row) <= max(idx_col1, idx_col2):
                    continue
                name = fundname_to_corpname(extract_bonken_numbers(row[idx_col1]))
                amount = parse_number(row[idx_col2])
                if not name or is_summary_row_name(name):
                    continue
                first_table_filtered.append({"발행 대상자명": name, "권면": amount})
    
    if second_table is not None:
        tbody = second_table.find(['tbody', 'TBODY'])
        if tbody:
            for tr in tbody.find_all(['tr', 'TR']):
                cells = tr.find_all(['td', 'TD', 'te', 'TE'])
                if cells:
                    row = [cell.get_text(strip=True) for cell in cells]
                    second_table_rows.append(row)

        if second_table_rows and len(second_table_rows[0]) >= 2:
            first_cell = str(second_table_rows[0][0])
            if not bool(re.search(r'\d', first_cell)):
                second_table_rows = second_table_rows[1:]

        '''
        First Table : corpname(safe) or bonken numbers | fiscal amount
        Second Table : bonken number | corpname
        '''

    if first_table is not None and second_table is not None:
        def map_numbers_to_corpnames(text):
            if '|' in text:
                first_num = text.split('|')[0].strip()
                if first_num.isdigit():
                    for row in second_table_rows:
                        if len(row) >= 2 and first_num in str(row[0]):
                            return fundname_to_corpname(str(row[1]))
                return text
            else:
                # Handle single number
                if text.isdigit():
                    for row in second_table_rows:
                        if len(row) >= 2 and text in str(row[0]):
                            return fundname_to_corpname(str(row[1]))
                return text
        
        if first_table_filtered:
            grouped = {}
            for row in first_table_filtered:
                name = map_numbers_to_corpnames(row["발행 대상자명"])
                grouped[name] = grouped.get(name, 0.0) + row["권면"]
            final_table = [
                {"발행 대상자명": name, "권면": amount}
                for name, amount in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
            ]
            total_amount = sum(row["권면"] for row in final_table) / 10**8
            
            result_text = format_final_table_text(final_table)
            return result_text, total_amount
    
    elif first_table is not None:
        total_amount = sum(row["권면"] for row in first_table_filtered) / 10**8
        return format_final_table_text(first_table_filtered), total_amount
        
    return "-", 0.0

test_cases = [
    '20220706000148', '20231027000166', '20240216000966', '20230508000614', 
    '20240604000386', '20240726000500', '20230807000401', '20230829000575', '20230920000049', 
    '20231027000378', '20231115000399', '20240117000341', '20240125000601', '20240329002828', 
    '20240402003067', '20250409001971', '20240605000268', '20240628000114', '20240827000618', 
    '20250827000516', '20240909000134', '20250916000305', '20250917000329', '20241016000313', 
    '20250912000464', '20250912000257', '20250915000241', '20240425000614', '20250922000288', 
    '20250219001783', '20250724000361', '20250729000174', '20250801000380', '20250807000166', 
    '20250905000042', '20250902000329', '20250908000110', '20250922000174', '20251015000373', 
    '20251001000656', '20250919000150'
]
