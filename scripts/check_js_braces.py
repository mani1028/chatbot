import re

path = 'templates/super_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Match <script> blocks that do NOT have a src attribute
script_pattern = re.compile(r'<script(?:(?!src=)[\s\S])*?>([\s\S]*?)</script>', re.IGNORECASE)
matches = list(script_pattern.finditer(content))

if not matches:
    print('No inline <script> blocks found')
    exit(0)

def check_block(block_text, start_line_offset):
    brace = 0
    in_single = in_double = in_back = in_comment = False
    lines = block_text.splitlines()
    for li, line in enumerate(lines):
        i = 0
        while i < len(line):
            ch = line[i]
            if not in_single and not in_double and not in_back:
                if not in_comment and ch == '/' and i+1 < len(line) and line[i+1] == '/':
                    break
                if not in_comment and ch == '/' and i+1 < len(line) and line[i+1] == '*':
                    in_comment = True
                    i += 2
                    continue
            if in_comment:
                if ch == '*' and i+1 < len(line) and line[i+1] == '/':
                    in_comment = False
                    i += 2
                    continue
                i += 1
                continue

            if ch == "'" and not in_double and not in_back:
                in_single = not in_single
                i += 1
                continue
            if ch == '"' and not in_single and not in_back:
                in_double = not in_double
                i += 1
                continue
            
            # Handle template literals and their ${} interpolations
            if ch == '`' and not in_single and not in_double:
                in_back = not in_back
                i += 1
                continue
            
            # Skip content inside template literal (including ${} expressions)
            if in_back:
                if ch == '\\':
                    i += 2
                    continue
                i += 1
                continue
            
            # Skip content inside regular strings
            if in_single or in_double:
                if ch == '\\':
                    i += 2
                    continue
                i += 1
                continue

            if ch == '{':
                brace += 1
            elif ch == '}':
                brace -= 1
                if brace < 0:
                    print(f'Imbalance: unexpected "}}" at line {start_line_offset + li + 1}:')
                    ctx_start = max(0, li - 4)
                    ctx_end = min(len(lines) - 1, li + 4)
                    print('--- Context ---')
                    for j in range(ctx_start, ctx_end + 1):
                        prefix = '>' if j == li else ' '
                        print(f"{prefix} {start_line_offset + j + 1}: {lines[j]}")
                    return False
            i += 1

    if brace != 0:
        print(f'Final brace count not zero in block starting at line {start_line_offset+1}: {brace} (positive means unclosed "{{")')
        return False
    print(f'Block starting at line {start_line_offset+1}: braces OK')
    return True

for m in matches:
    prefix = content[:m.start()]
    start_line = prefix.count('\n')
    block_text = m.group(1)
    ok = check_block(block_text, start_line)
    if not ok:
        exit(1)

print('All inline script blocks have balanced braces')
