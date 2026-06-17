import sys

def fix_whitespace(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Strip trailing whitespace and ensure newline
    fixed_lines = [line.rstrip() + '\n' for line in lines]
    
    # Ensure file ends with exactly one newline
    while len(fixed_lines) > 0 and fixed_lines[-1] == '\n':
        fixed_lines.pop()
    if len(fixed_lines) > 0:
        if not fixed_lines[-1].endswith('\n'):
            fixed_lines[-1] += '\n'
    else:
        fixed_lines = ['\n']

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

fix_whitespace('backend/department_router.py')
fix_whitespace('backend/timetable_pipeline.py')

print('Whitespace fixed.')
