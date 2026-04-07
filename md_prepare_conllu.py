with open('manual-dix/grc.conllu', 'w') as fout:
    for mode in ['dev', 'test', 'train']:
        with open(f'ud-treebanks-v2.17/UD_Ancient_Greek-PTNK/grc_ptnk-ud-{mode}.conllu') as fin:
            fout.write(fin.read())

with open('manual-dix/hbo.conllu', 'w') as fout:
    for mode in ['dev', 'test', 'train']:
        with open(f'ud-treebanks-v2.17/UD_Ancient_Hebrew-PTNK/hbo_ptnk-ud-{mode}.conllu') as fin:
            for block in fin.read().split('\n\n'):
                if not ('Genesis' in block or 'Ruth' in block):
                    continue
                if '31:51' in block:
                    continue
                if '32:33' in block:
                    continue
                if '35:21' in block:
                    continue
                fout.write(block + '\n\n')
