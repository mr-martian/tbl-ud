import sys

for line in sys.stdin:
    out = ''
    state = 'blank'
    for i, c in enumerate(line):
        out += c
        if c == '^' and state == 'blank':
            state = 'src'
        elif c == '/' and state != 'blank':
            state = 'tgt'
        elif c == '<' and state != 'blank' and line[i+1] not in '@#':
            out += state + ':'
        elif c == '$' and state != 'blank':
            state = 'blank'
    sys.stdout.write(out)
    sys.stdout.flush()

