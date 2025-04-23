import re
import sys

skip = re.compile(sys.argv[1])

cur = ''
for line in sys.stdin:
    cur += line
    if not line.strip():
        if cur and not skip.search(cur):
            print(cur, end='')
        cur = ''
if cur and not skip.search(cur):
    print(cur, end='')
