import glob
from collections import defaultdict, Counter

with_rules = defaultdict(list)
no_rules = defaultdict(list)

for fname in glob.glob('cv_data/*/dev.*.eval.log'):
    dix = 'Gloss' if '_g_' in fname else 'MACULA'
    tmpl = 'Strict' if '13' in fname else 'Loose'
    align = None
    if 'eflomal' in fname:
        align = 'Eflomal'
        if 'eflomal_feat' in fname:
            align = 'Joint'
    else:
        align = 'Features'
    raw = 'raw' in fname
    uas = 0
    las = 0
    with open(fname) as fin:
        for line in fin:
            if line.startswith('UAS'):
                uas = float(line.split()[-1])
            elif line.startswith('LAS'):
                las = float(line.split()[-1])
    if raw:
        no_rules[(dix, tmpl, align)].append((uas, las))
    else:
        with_rules[(dix, tmpl, align)].append((uas, las))

for key in sorted(with_rules.keys()):
    u0 = max([x[0] for x in no_rules[key]])
    l0 = max([x[1] for x in no_rules[key]])
    u1 = max([x[0] for x in with_rules[key]])
    l1 = max([x[1] for x in with_rules[key]])
    print('   ', ' & '.join(key), f'& {u0:.2f} & {l0:.2f} & {u1:.2f} & {l1:.2f} \\\\')
