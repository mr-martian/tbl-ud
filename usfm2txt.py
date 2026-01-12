import argparse
import glob
import re

parser = argparse.ArgumentParser()
parser.add_argument('version')
parser.add_argument('split')
args = parser.parse_args()

verse_re = re.compile(r'^# sent_id = Masoretic-([A-Za-z]+)-(\d+):([\d-]+)-hbo$')

verses = []

with open(glob.glob(f'/home/daniel/hbo-UD/UD_Ancient_Hebrew-PTNK/*{args.split}*.conllu')[0]) as fin:
    for line in fin:
        if 'sent_id' in line:
            m = verse_re.match(line.strip())
            if not m:
                raise ValueError(f'weird sent_id {line.strip()}')
            if '-' in m.group(3):
                v1, v2 = m.group(3).split('-')
                verses.append((m.group(1), int(m.group(2)),
                               int(v1), int(v2)))
            else:
                verses.append((m.group(1), int(m.group(2)),
                               int(m.group(3)), int(m.group(3))))

v_re = re.compile(r'\\v \d+')
strong_re = re.compile(r'\|strong="H\d+"\\\+?w\*')
other_cmd = re.compile(r'\\\+?(nd|w|p|sc)\*?')
def parse_line(line):
    line = v_re.sub('', line)
    line = strong_re.sub('', line)
    line = other_cmd.sub('', line)
    line = line.replace('“', '"')
    line = line.replace('”', '"')
    line = line.replace("’", "'")
    line = line.replace("‘", "'")
    return line.split()

verse_idx = 0
books = [('02', 'Genesis'), ('03', 'Exodus'),
         ('04', 'Leviticus'), ('05', 'Numbers'),
         ('06', 'Deuteronomy'), ('09', 'Ruth')]
chapter = 0
verse = 0
def include():
    if verse_idx >= len(verses):
        return False
    v = verses[verse_idx]
    return v[1] == chapter and v[2] <= verse <= v[3]
for pfx, book in books:
    if verse_idx >= len(verses):
        break
    if book != verses[verse_idx][0]:
        continue
    words = []
    for fname in glob.glob(f'{args.version}/{pfx}*.usfm'):
        with open(fname) as fin:
            for line in fin:
                if line.startswith(r'\c'):
                    chapter = int(line.split()[1])
                elif line.startswith(r'\p'):
                    if include():
                        words += parse_line(line)
                elif line.startswith(r'\v'):
                    verse = int(line.split()[1])
                    if not include() and words:
                        print(' _ '.join(words))
                        words = []
                        verse_idx += 1
                    if verse == 1:
                        while verse_idx < len(verses) and chapter == verses[verse_idx][1] + 1:
                            print('null')
                            verse_idx += 1
                    if include():
                        words += parse_line(line)
    if words:
        print(' _ '.join(words))
        words = []
        verse_idx += 1
