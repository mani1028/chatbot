import re

path = 'templates/super_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Match <script> blocks that do NOT have a src attribute
script_pattern = re.compile(r'<script(?:(?!src=)[\s\S])*?>([\s\S]*?)</script>', re.IGNORECASE)
matches = list(script_pattern.finditer(content))

def trace_braces(block_text, start_line_offset):
    brace = 0
    in_single = in_double = in_back = in_comment = False
    lines = block_text.splitlines()
    events = []
    
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
                event = f'Line {start_line_offset + li + 1}: OPEN {{ → count={brace}'
                events.append((start_line_offset + li + 1, brace, event))
            elif ch == '}':
                brace -= 1
                event = f'Line {start_line_offset + li + 1}: CLOSE }} → count={brace}'
                events.append((start_line_offset + li + 1, brace, event))
                if brace < 0:
                    print(f'\nERROR: Brace went negative!')
                    for line_num, count, evt in events[-10:]:
                        print(evt)
                    return False
            i += 1
    
    # Print events with major changes
    print('\nBrace transition events (gaps of 100+ lines):')
    prev_line = 0
    for line_num, count, evt in events:
        if line_num - prev_line > 100 or line_num < 200 or (line_num > 4100 and line_num < 4150):
            print(evt)
        prev_line = line_num
    
    print(f'\nFinal brace count: {brace}')
    if brace > 0:
        print(f'Last 5 opening braces:')
        opened_braces = [(ln, ct, ev) for ln, ct, ev in events if 'OPEN' in ev]
        for line_num, count, evt in opened_braces[-5:]:
            print(f'  {evt}')
    return True

# Check block 2 (the large one)
m = matches[1]
prefix = content[:m.start()]
start_line = prefix.count('\n')
block_text = m.group(1)
trace_braces(block_text, start_line)
