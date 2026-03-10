import re

path = 'templates/super_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check block 2 (the large one with the error)
script_start = 1735 - 1  #0-indexed
script_end = 4172  # approx

block_lines = lines[script_start:script_end]

brace = 0
in_single = in_double = in_back = in_comment = False
unclosed_braces = []

for li, line in enumerate(block_lines):
    i = 0
    while i < len(line):
        ch = line[i]
        
        # Skip comments
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

        # Handle quotes
        if ch == "'" and not in_double and not in_back:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single and not in_back:
            in_double = not in_double
            i += 1
            continue
        if ch == '`' and not in_single and not in_double:
            in_back = not in_back
            i += 1
            continue
        
        # Skip string content
        if in_back or in_single or in_double:
            if ch == '\\':
                i += 2
                continue
            i += 1
            continue

        if ch == '{':
            brace += 1
            unclosed_braces.append((script_start + li + 1, i+1, brace))
        elif ch == '}':
            brace -= 1
            if unclosed_braces:
                unclosed_braces.pop()

        i += 1

print(f'Final brace count: {brace}')
if unclosed_braces:
    print(f'\nUnclosed braces (total: {len(unclosed_braces)}):')
    for line_num, col, count_at_open in unclosed_braces[-5:]:
        # Print that line
        line_idx = line_num - 1 - script_start
        if 0 <= line_idx < len(block_lines):
            content = block_lines[line_idx].rstrip()
            print(f'  Line {line_num}, col {col}: {content[:80]}')
