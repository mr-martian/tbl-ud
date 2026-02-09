from linearize import *

@dataclass
class Sentence(BaseSentence):
    alignments: dict = field(default_factory=dict)

    def preprocess(self):
        ttags = defaultdict(list)
        all_ttags = []
        for i, w in enumerate(self.target):
            tags = set() if w.feats == '_' else set(w.feats.split('|'))
            ttags[('"'+w.lemma+'"', w.upos)].append((i, tags))
            all_ttags.append((i, tags | {w.lemma, w.upos}))
        for cohort in self.source.cohorts:
            reading = utils.primary_reading(cohort)
            key = set([t for t in reading.tags[1:] if '=' in t])
            comp = ttags[(reading.lemma, reading.tags[0])]
            if not comp:
                comp = all_ttags
                key |= {reading.lemma, reading.tags[0]}
            options = defaultdict(list)
            for i, tg in comp:
                options[(len(tg & key), max(len(tg | key), 1))].append(i)
            ls = sorted(options.keys(), key=lambda x: x[0]/x[1])
            if ls:
                self.alignments[cohort.dep_self] = options[ls[-1]]

    def before(self, a, b):
        # is a unambiguously before b in the target data?
        if not self.alignments.get(a) or not self.alignments.get(b):
            return False
        return self.alignments[a][-1] < self.alignments[b][0]

@dataclass
class Trainer(BaseTrainer):
    sentence_class = Sentence

if __name__ == '__main__':
    t = Trainer()
    t.cli()
