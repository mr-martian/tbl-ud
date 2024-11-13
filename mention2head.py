from udapi.core.block import Block

class Mention2Head(Block):
    def process_coref_mention(self, mention):
        heads = [w for w in mention.words
                 if not any(w.is_descendant_of(w2) for w2 in mention.words)]
        head = heads[0]
        head.misc['Type'] = mention.entity.etype
