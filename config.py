# config.py
"""
글로벌 설정 파일
- 팀 구성 정보 (TEAM_RAW)
- 이름 → 팀 매핑 (NAME2TEAM)
- 조직 구조 (그룹장/팀장/파트 정보)
"""

import re

# ────────── 조직 구조 ──────────

# 그룹장
GROUP_LEADER = '박종협'

# 팀장 매핑
TEAM_LEADERS = {
    '기업교육 1팀': '김별',
    '기업교육 2팀': '정선희',
}

# 파트 구성 (팀 → 파트 → 멤버 리스트)
PART_STRUCTURE = {
    '기업교육 1팀': {
        '1파트': ['김솔이', '황초롱', '김정은', '김동찬', '정태윤', '서정연'],
        '2파트': ['강지선', '정하영', '박범규', '하승민', '이은서'],
    },
    '기업교육 2팀': {
        '1파트': ['권노을', '이윤지B', '이현진', '김민선', '강연정', '방신우', '홍제환'],
        '2파트': ['정다혜', '임재우', '송승희', '손승완', '김윤지', '손지훈', '홍예진'],
        '온라인셀': ['강진우', '강다현', '이수빈'],
    },
}

# ────────── 팀 구성 정보 (하위 호환성 유지) ──────────

# 팀별 전체 멤버 리스트 (팀장 + 파트 멤버)
TEAM_RAW = {
    '기업교육 1팀': [
        TEAM_LEADERS['기업교육 1팀'],  # 팀장
        *PART_STRUCTURE['기업교육 1팀']['1파트'],
        *PART_STRUCTURE['기업교육 1팀']['2파트'],
    ],
    '기업교육 2팀': [
        TEAM_LEADERS['기업교육 2팀'],  # 팀장
        *PART_STRUCTURE['기업교육 2팀']['1파트'],
        *PART_STRUCTURE['기업교육 2팀']['2파트'],
        *PART_STRUCTURE['기업교육 2팀']['온라인셀'],
    ],
}

# 이름 → 팀 매핑 (자동 생성)
# 'B'로 끝나는 이름에서 'B' 제거 후 매핑
NAME2TEAM = {re.sub(r'B$','', n): t for t, lst in TEAM_RAW.items() for n in lst}

# 이름 → 파트 매핑 (자동 생성)
NAME2PART = {}
for team, parts in PART_STRUCTURE.items():
    for part, members in parts.items():
        for member in members:
            name_key = re.sub(r'B$','', member)
            NAME2PART[name_key] = f"{team} {part}"

# 팀장도 파트에 매핑 (팀장은 '팀장'으로 표시)
for team, leader in TEAM_LEADERS.items():
    name_key = re.sub(r'B$','', leader)
    NAME2PART[name_key] = f"{team} 팀장"

# 그룹장 매핑
name_key = re.sub(r'B$','', GROUP_LEADER)
NAME2PART[name_key] = "기업교육그룹장"

# 팀 목록
TEAMS = list(TEAM_RAW.keys())

# ────────── 헬퍼 함수 ──────────

def get_team_members(team_name: str) -> list[str]:
    """팀의 전체 멤버 리스트 반환 (팀장 포함)"""
    return TEAM_RAW.get(team_name, [])

def get_part_members(team_name: str, part_name: str) -> list[str]:
    """특정 파트의 멤버 리스트 반환"""
    return PART_STRUCTURE.get(team_name, {}).get(part_name, [])

def get_team_leader(team_name: str) -> str:
    """팀장 이름 반환"""
    return TEAM_LEADERS.get(team_name, '')

def get_person_role(name: str) -> str:
    """사람의 역할 반환 (그룹장/팀장/파트)"""
    name_key = re.sub(r'B$','', name)
    if name_key == re.sub(r'B$','', GROUP_LEADER):
        return "기업교육그룹장"
    elif name_key in [re.sub(r'B$','', leader) for leader in TEAM_LEADERS.values()]:
        team = NAME2TEAM.get(name_key, '')
        return f"{team} 팀장"
    else:
        return NAME2PART.get(name_key, '')

