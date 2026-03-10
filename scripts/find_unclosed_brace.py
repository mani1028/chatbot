import re

path = 'templates/super_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Match <script> blocks that do NOT have a src attribute
script_pattern = re.compile(r'<script(?:(?!src=)[\s\S])*?>([\s\S]*?)</script>', re.IGNORECASE)
matches = list(script_pattern.finditer(content))

def check_block_find_unclosed(block_text, start_line_offset):
    brace = 0
    brace_stack = []  # Track opening braces with their line numbers
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
            
            if ch == '`' and not in_single and not in_double:
                in_back = not in_back
                i += 1
                continue
            
            if in_back:
                if ch == '\\':
                    i += 2
                    continue
                i += 1
                continue
            
            if in_single or in_double:
                if ch == '\\':
                    i += 2
                    continue
                i += 1
                continue

            if ch == '{':
                brace += 1
                brace_stack.append((start_line_offset + li + 1, i + 1))
            elif ch == '}':
                brace -= 1
                if brace_stack:
                    brace_stack.pop()
            i += 1

    if brace != 0:
        print(f'\nBlock starting at line {start_line_offset+1}:')
        print(f'Final brace count: {brace}')
        if brace > 0:
            print(f'\n{brace} unclosed braces. Last unclosed brace(s):')
            for line_num, col in brace_stack[-min(3, len(brace_stack)):]:
                print(f'  Line {line_num}, column {col}')
                # Print that line
                actual_idx = line_num - start_line_offset - 1
                if 0 <= actual_idx < len(lines):
                    print(f'    {lines[actual_idx][:100]}')
        return False
    return True

for block_num, m in enumerate(matches, 1):
    prefix = content[:m.start()]
    start_line = prefix.count('\n')
    block_text = m.group(1)
    ok = check_block_find_unclosed(block_text, start_line)
    if not ok:
        break
