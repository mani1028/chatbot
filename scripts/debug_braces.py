import re

path = 'templates/super_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Match <script> blocks that do NOT have a src attribute
script_pattern = re.compile(r'<script(?:(?!src=)[\s\S])*?>([\s\S]*?)</script>', re.IGNORECASE)
matches = list(script_pattern.finditer(content))

def check_block_verbose(block_text, start_line_offset, block_num):
    brace = 0
    in_single = in_double = in_back = in_comment = False
    lines = block_text.splitlines()
    print(f'\n=== Block {block_num} starts at line {start_line_offset+1} ===')
    
    for li, line in enumerate(lines):
        i = 0
        line_brace_start = brace
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
            elif ch == '}':
                brace -= 1
                if brace < 0:
                    print(f'\nERROR at line {start_line_offset + li + 1}:')
                    print(line)
                    print(f'Brace count went negative! Was {line_brace_start}, now {brace}')
                    return False
            i += 1
        
        if brace != line_brace_start or li % 100 == 0:
            if li % 100 == 0 and li > 0:
                print(f'Line {start_line_offset + li + 1}: brace count = {brace}')

    print(f'\nBlock {block_num} final brace count: {brace}')
    if brace != 0:
        print(f'WARNING: Braces not balanced! Unclosed: {brace}')
        # Print last 10 lines to see where it ends badly
        print('Last 10 lines of block:')
        for j in range(max(0, len(lines)-10), len(lines)):
            print(f'{start_line_offset + j + 1}: {lines[j]}')
        return False
    return True

for block_num, m in enumerate(matches, 1):
    prefix = content[:m.start()]
    start_line = prefix.count('\n')
    block_text = m.group(1)
    ok = check_block_verbose(block_text, start_line, block_num)
    if not ok:
        break
