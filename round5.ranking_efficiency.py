import timeit
import collections
import sqlite3

def sql():
    con = sqlite3.connect('hbo-grc.db')
    cur = con.cursor()
    cur.execute('CREATE INDEX blah ON context (rule)')
    cur.execute('SELECT COUNT(*) as ct, rule, relation FROM context GROUP BY rule ORDER BY ct DESC LIMIT 100')
    cur.fetchall()

def count():
    con = sqlite3.connect('hbo-grc.db')
    cur = con.cursor()
    cur.execute('SELECT rule, relation FROM context')
    ct = collections.Counter()
    for row in cur:
        ct[row] += 1
    print(ct.most_common(100))

print(timeit.timeit('sql()', globals=globals(), number=1))
#print(timeit.timeit('count()', globals=globals(), number=1))
