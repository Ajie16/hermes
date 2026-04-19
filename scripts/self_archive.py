#!/usr/bin/env python3
"""
Self-Archive Script - 自动从 cron output 提取完整 diary 信息并更新经验索引

解决 generator.py 的 learnings 提取问题：
- generator.py 只匹配 - [ ] checkbox 格式
- 实际日记使用纯 - 列表格式
- 这个脚本在后处理阶段修复这个问题

用法: python3 self_archive.py
"""
import os
import re
import json
from datetime import datetime
from pathlib import Path

HERMES_HOME = Path.home() / ".hermes"
CRON_OUTPUT_DIR = HERMES_HOME / "cron/output/c33aac8ca375"
DATA_DIR = HERMES_HOME / "web_dashboard/public/data"
LEARNINGS_PATH = HERMES_HOME / "skills/self-improving-agent/LEARNINGS.md"
ERRORS_PATH = HERMES_HOME / "skills/self-improving-agent/ERRORS.md"
EXP_INDEX_PATH = HERMES_HOME / "skills/self-improving-agent/EXPERIENCE_INDEX.json"
DIARY_DATA_PATH = DATA_DIR / "diary.json"


def find_latest_execution():
    """Find the most recent valid cron execution file."""
    if not CRON_OUTPUT_DIR.exists():
        return None, None
    
    files = sorted(CRON_OUTPUT_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files:
        if f.stat().st_size < 1000:
            continue
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
            
            # Skip pure prompt templates
            if '## Prompt' in content[:2000] and '## Response' not in content[-5000:]:
                continue
            if '## Response' in content or '📊 Run #' in content:
                return f, content
        except Exception:
            continue
    return None, None


def extract_run_header_positions(content):
    """Find all '📊 Run #X' header positions in content."""
    positions = []
    for i, line in enumerate(content.split('\n'), 1):
        m = re.match(r'^#{1,2}\s*[📊📝]\s*Run\s*#\s*(\d+)\s*(?:执行总结|总结)?', line)
        if m:
            positions.append((i, int(m.group(1))))
    return positions


def extract_plain_list_items(section_content):
    """
    Extract list items from section content.
    Handles BOTH checkbox (- [x]) AND plain (-) formats.
    
    generator.py only handles checkbox format - this fixes that.
    """
    items = []
    for line in section_content:
        line = line.strip()
        if not line:
            continue
        # Checkbox format: - [ ] item or - [x] item
        m = re.match(r'^-\s*\[[ x]\]\s*(.+)', line)
        if m:
            items.append(m.group(1).strip())
            continue
        # Plain list format: - item (but not --- or other hr-like)
        m = re.match(r'^-\s+(.+)$', line)
        if m and not line.startswith('---'):
            items.append(m.group(1).strip())
    return items


# Use simple substring matching - much more robust than emoji patterns
SECTION_KEYWORDS = {
    'thinking': '思考过程',
    'action': '执行行动',
    'result': '执行结果',
    'learnings': '学习收获',
    'next_plan': '下次计划',
    'errors': '错误记录',
}


def find_section_headers(lines):
    """Find all section header line indices using keyword matching."""
    headers = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith('#'):
            continue
        for sec_name, keyword in SECTION_KEYWORDS.items():
            if keyword in stripped:
                headers[sec_name] = i
                break
    return headers


def parse_diary_content(content):
    """Parse diary content from cron output - FIXED learnings extraction."""
    # Find the last "## Response" section (actual execution output)
    response_start = content.rfind('## Response')
    if response_start == -1:
        response_start = content.rfind('📊 Run #')
    
    if response_start > 0:
        response_content = content[response_start:]
    else:
        response_content = content
    
    lines = response_content.split('\n')
    
    thinking = action = result = learnings_str = errors_str = next_plan = ""
    learnings = []
    errors_encountered = []
    cycle = None
    timestamp = None
    
    # Find all section headers
    headers = find_section_headers(lines)
    print(f"  Found sections: {list(headers.keys())}")
    
    # Process each section
    section_order = ['thinking', 'action', 'result', 'learnings', 'next_plan', 'errors']
    prev_idx = 0
    
    for sec_name in section_order:
        if sec_name not in headers:
            continue
        
        start_idx = headers[sec_name]
        
        # Get content between this header and the next
        section_lines = []
        for i in range(start_idx + 1, len(lines)):
            # Stop at next section header
            stripped = lines[i].strip()
            is_header = False
            for keyword in SECTION_KEYWORDS.values():
                if stripped.startswith('#') and keyword in stripped:
                    is_header = True
                    break
            if is_header:
                break
            section_lines.append(lines[i])
        
        section_text = '\n'.join(section_lines).strip()
        
        if sec_name == 'thinking': thinking = section_text
        elif sec_name == 'action': action = section_text
        elif sec_name == 'result': result = section_text
        elif sec_name == 'learnings':
            learnings_str = section_text
            learnings = extract_plain_list_items(section_lines)
        elif sec_name == 'next_plan':
            next_plan = section_text
        elif sec_name == 'errors':
            errors_str = section_text
            errors_encountered = extract_plain_list_items(section_lines)
    
    # Extract cycle and timestamp
    header_positions = extract_run_header_positions(content)
    if header_positions:
        section_start, cycle = header_positions[-1]
    
    ts_match = re.search(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})', content[-3000:])
    if ts_match:
        timestamp = ts_match.group(1).replace('T', ' ')
        try:
            timestamp = datetime.strptime(timestamp[:19], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
    else:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return {
        'cycle': cycle or 0,
        'timestamp': timestamp,
        'thinking': thinking[:2000],
        'action': action[:2000],
        'result': result[:2000],
        'learnings': learnings[:10],
        'errors_encountered': errors_encountered[:10],
        'next_plan': next_plan[:500],
    }


def update_experience_index(diary, source_file):
    """Update the EXPERIENCE_INDEX.json with the latest diary entry."""
    if not EXP_INDEX_PATH.parent.exists():
        EXP_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    if EXP_INDEX_PATH.exists():
        with open(EXP_INDEX_PATH) as f:
            exp_index = json.load(f)
    else:
        exp_index = {"learnings": [], "errors": [], "workflows": []}
    
    new_entry = {
        "cycle": diary.get('cycle', 0),
        "timestamp": diary.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        "date": diary.get('timestamp', '')[:10] if diary.get('timestamp') else datetime.now().strftime('%Y-%m-%d'),
        "time": diary.get('timestamp', '')[11:16] if diary.get('timestamp') else datetime.now().strftime('%H:%M'),
        "action_summary": (diary.get('action', '') or diary.get('result', ''))[:60],
        "key_learnings": diary.get('learnings', [])[:5],
        "errors_encountered": diary.get('errors_encountered', [])[:3],
        "tools_used": [],
        "diary_file": str(source_file) if source_file else "",
        "data_file": str(DIARY_DATA_PATH)
    }
    
    exp_index["learnings"] = [e for e in exp_index.get("learnings", []) if e.get("cycle") != diary.get('cycle')]
    exp_index["learnings"].insert(0, new_entry)
    exp_index["learnings"] = exp_index["learnings"][:50]
    
    with open(EXP_INDEX_PATH, 'w') as f:
        json.dump(exp_index, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ EXPERIENCE_INDEX updated: {len(exp_index['learnings'])} entries")


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running self-archive script...")
    
    source_file, content = find_latest_execution()
    if source_file is None:
        print("  ⚠️ No valid execution file found")
        return
    
    print(f"  📄 Found: {source_file.name}")
    
    diary = parse_diary_content(content)
    print(f"  Cycle: {diary.get('cycle')}")
    print(f"  Learnings found: {len(diary.get('learnings', []))}")
    print(f"  Errors found: {len(diary.get('errors_encountered', []))}")
    
    if diary.get('learnings'):
        for l in diary['learnings'][:5]:
            print(f"    - {l[:80]}")
    
    existing_diary = {}
    if DIARY_DATA_PATH.exists():
        try:
            with open(DIARY_DATA_PATH) as f:
                existing_diary = json.load(f)
        except:
            pass
    
    for key in ['cycle', 'timestamp', 'thinking', 'action', 'result', 'learnings', 'errors_encountered', 'next_plan']:
        if diary.get(key):
            existing_diary[key] = diary[key]
    
    with open(DIARY_DATA_PATH, 'w') as f:
        json.dump(existing_diary, f, ensure_ascii=False, indent=2)
    print(f"  ✅ diary.json updated")
    
    update_experience_index(diary, source_file)
    
    print(f"  ✅ Self-archive complete!")


if __name__ == "__main__":
    main()
