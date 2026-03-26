import cg3
import concurrent.futures
import json
import glob
import metrics
import os
import utils

def load_cg(fname):
    with open(fname, 'rb') as fin:
        return list(cg3.parse_binary_stream(fin, windows_only=True))
targets = {
    'grc': load_cg('generated/hbo-grc/grc.dev.bin'),
    'eng': load_cg('generated/hbo-eng/eng.NET.dev.bin'),
    'blx': load_cg('generated/blx/blx.dev.bin'),
}
skips = {
    'grc': set(),
    'eng': utils.load_json_set('generated/hbo-eng/eng.NET.dev.skip.json'),
    'blx': utils.load_json_set('generated/blx/blx.dev.skip.json'),
}
feats = {
    'grc': utils.load_json_set('generated/hbo-grc/grc.train.feats.json'),
    'eng': utils.load_json_set('generated/hbo-eng/eng.feats.json'),
    'blx': utils.load_json_set('generated/blx/blx.feats.json'),
}

def steps(datadir):
    name = os.path.basename(datadir)
    pieces = name.split('_')
    step = int(pieces[-3])
    n = 200 - step
    results = sorted(glob.glob(os.path.join(datadir, 'dev.*.bin')))
    for r in results:
        n += step
        yield n, r

def eval_grammar(datadir):
    x = []
    y_lem = []
    y_form = []
    tgt = next(v for k, v in targets.items() if k in datadir)
    skip = next(v for k, v in skips.items() if k in datadir)
    feat = next(v for k, v in feats.items() if k in datadir)
    for n, infile in steps(datadir):
        src = load_cg(infile)
        l, f = metrics.PER(src, tgt,
                           target_features=feat, skip_windows=skip)
        x.append(n)
        y_lem.append(l)
        y_form.append(f)
    with open(os.path.join(datadir, 'eval.log.json'), 'w') as fout:
        fout.write(json.dumps({'x': x, 'y_lem': y_lem, 'y_form': y_form}))

with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = []
    for datadir in glob.glob('pipe-st/*'):
        print(datadir)
        futures.append(executor.submit(eval_grammar, datadir))
    for future in concurrent.futures.as_completed(futures):
        pass
