from dataclasses import dataclass, field
import struct

@dataclass
class Reading:
    lemma: str
    tags: list[str]

@dataclass
class Cohort:
    source: Reading
    target: list[Reading]
    dep_self: int
    dep_head: int

@dataclass
class Sentence:
    words: list[Cohort]

def parse_block(buf):
    pos = 0
    def read_pat(pat):
        nonlocal pos, buf
        ret = struct.unpack_from('<'+pat, buf, pos)
        pos += struct.calcsize('<'+pat)
        return ret
    def read_u16():
        return read_pat('H')[0]
    def read_u32():
        return read_pat('I')[0]
    def read_str():
        l = read_u16()
        if l == 0:
            return b''
        return read_pat(f'{l}s')[0]
        return s
    read_u16() # window flags
    tag_count = read_u16()
    tags = [read_str().decode('utf-8') for i in range(tag_count)]
    def read_tags():
        nonlocal tags
        ct = read_u16()
        if ct == 0:
            return []
        idx = read_pat(f'{ct}H')
        return [tags[t] for t in idx]
    assert(read_u16() == 0) # vars
    read_str() # text
    read_str() # text_post
    cohort_count = read_u16()
    words = []
    for i in range(cohort_count):
        read_u16() # flags
        wf = tags[read_u16()]
        src = Reading(wf, read_tags())
        ds = read_u32()
        dp = read_u32()
        if dp == 0xffffffff:
            dp = None
        rel_count = read_u16()
        for i in range(rel_count):
            # TODO
            read_u16() # tag
            read_u32() # head
        read_str() # text
        read_str() # wblank
        readings = []
        reading_count = read_u16()
        for i in range(reading_count):
            read_u16() # flags
            lm = tags[read_u16()]
            readings.append(Reading(lm, read_tags()))
        words.append(Cohort(src, readings, ds, dp))
    return Sentence(words)

with open('/home/daniel/apertium/cg3/out.bin', 'rb') as fin:
    fin.read(8)
    for i in range(1):
        lb = fin.read(4)
        ln = struct.unpack('<I', lb)[0]
        print(parse_block(fin.read(ln)))

