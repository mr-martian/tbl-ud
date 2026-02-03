from collections import defaultdict, Counter
import struct

u16_reader = struct.Struct('<H')
u32_reader = struct.Struct('<I')

def parse_window(buf, target_feats):
    words = Counter()
    #feats = defaultdict(lambda: defaultdict(Counter))
    feats = Counter()
    counts = Counter()
    pos = 5 # skip length header
    def read_pat(pat):
        nonlocal pos, buf
        ret = struct.unpack_from('<'+pat, buf, pos)
        pos += struct.calcsize('<'+pat)
        return ret
    def read_u16():
        nonlocal pos
        ret = u16_reader.unpack_from(buf, pos)[0]
        pos += 2
        return ret
    def read_u32():
        nonlocal pos
        ret = u32_reader.unpack_from(buf, pos)[0]
        pos += 4
        return ret
    def read_str():
        l = read_u16()
        if l == 0:
            return ''
        return read_pat(f'{l}s')[0].decode('utf-8')
    pos += 2 # flags
    tag_count = read_u16()
    tags = []
    feat_pairs = {}
    known_feats = set()
    ins = None
    src = None
    for i in range(tag_count):
        tags.append(read_str())
        if '=' in tags[-1]:
            k, v = tags[-1].split('=', 1)
            if not target_feats or k in target_feats:
                #feat_pairs[i] = (k, v)
                known_feats.add(i)
        elif tags[-1] == '"<ins>"':
            ins = i
        elif tags[-1] == 'SOURCE':
            src = i
    skip = read_u16()
    pos += skip * 5 # vars
    skip = read_u16()
    pos += skip # text
    skip += read_u16()
    pos += skip # text_post
    cohort_count = read_u16()
    counts['cohort'] = cohort_count
    for i in range(cohort_count):
        pos += 2 # skip flags
        surf = read_u16()
        if surf == ins:
            counts['ins'] += 1
        skip = read_u16()
        pos += 2 * skip # skip static tags
        pos += 8 # skip dep
        skip = read_u16()
        pos += 6 * skip # skip rel
        skip = read_u16()
        pos += skip # skip text
        skip = read_u16()
        pos += skip # skip wblank
        reading_count = read_u16()
        for i in range(reading_count):
            subreading = (read_u16() & 1)
            lem = read_u16()
            tags_count = read_u16()
            tag_ids = struct.unpack_from(f'<{tags_count}H', buf, pos)
            pos += 2 * tags_count
            if subreading:
                continue
            if not tag_ids:
                continue
            if tag_ids[0] == src:
                continue
            counts['reading'] += 1
            if tags[lem].startswith('"@'):
                counts['unk'] += 1
            key = tags[lem] + ' ' + tags[tag_ids[0]]
            words[key] += 1
            for t in tag_ids:
                if t in known_feats:
                    feats[(key, tags[t])] += 1
    return words, feats, counts

def iter_blocks(buf):
    pos = 8
    while pos < len(buf):
        if buf[pos] == 1:
            ln = u32_reader.unpack_from(buf, pos+1)[0]
            yield buf[pos:pos+ln+5]
            pos += ln + 5
        elif buf[pos] == 2:
            pos += 2
        elif buf[pos] == 3:
            ln = u32_reader.unpack_from(buf, pos+1)[0]
            pos += ln + 5

def symmetric_difference(d1, d2):
    t1, t2 = 0, 0
    for k, v1 in d1.items():
        v2 = d2[k]
        if v1 > v2:
            t1 += v1 - v2
        else:
            t2 += v2 - v1
    for k, v2 in d2.items():
        if k not in d1:
            t2 += v2
    return t1, t2
