import cg3
import concurrent.futures
import io
import json
import glob
import metrics
import os
import subprocess
import tempfile
import utils

source_files = {
    'grc_g': 'generated/hbo-grc/hbo.dev.bin',
    'grc_m': 'generated/hbo-grc/hbo-macula.dev.bin',
    'eng': 'generated/hbo-eng/hbo.NET.dev.bin',
    'blx': 'generated/blx/hbo.blx.dev.bin',
}
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

def blocks(grammar):
    name = os.path.basename(grammar)
    pieces = name.split('.')[0].split('_')
    step = int(pieces[-3])
    n = 200 - step
    with open(grammar) as fin:
        cur = ''
        for line in fin:
            if line.startswith('##') and ' 0:' in line:
                if n >= 200:
                    yield n, cur
                n += step
            cur += line
        yield n, cur

def eval_grammar(tmpdir, grammar):
    out = os.path.join(tmpdir, os.path.basename(grammar))
    x = []
    y_lem = []
    y_form = []
    src = next(v for k, v in source_files.items() if k in grammar)
    tgt = next(v for k, v in targets.items() if k in grammar)
    skip = next(v for k, v in skips.items() if k in grammar)
    feat = next(v for k, v in feats.items() if k in grammar)
    for n, block in blocks(grammar):
        with open(out, 'w') as fout:
            fout.write(block)
        proc = subprocess.run(['vislcg3', '--in-binary', '--out-binary',
                               '-g', out, '-I', src],
                              capture_output=True)
        l, f = metrics.PER(
            list(cg3.parse_binary_stream(
                io.BytesIO(proc.stdout), windows_only=True)),
            tgt, target_features=feat, skip_windows=skip)
        x.append(n)
        y_lem.append(l)
        y_form.append(f)
    with open(grammar+'.log.json', 'w') as fout:
        fout.write(json.dumps({'x': x, 'y_lem': y_lem, 'y_form': y_form}))

with (concurrent.futures.ThreadPoolExecutor() as executor,
      tempfile.TemporaryDirectory() as tmpdir):
    futures = []
    for grammar in glob.glob('st-output/*.cg3'):
        futures.append(executor.submit(eval_grammar, tmpdir, grammar))
    for future in concurrent.futures.as_completed(futures):
        pass
