import os
import config
import logging
import text2num
import cPickle as pickle

from gensim.models import Word2Vec, word2vec, Doc2Vec, doc2vec
from pattern.en import parsetree, pprint, singularize, wordnet


class D2V(object):
    DOC2VEC_MODEL = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'doc2vec.model')
    DOC2VEC_DATA = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'doc2vec.pickle')
    def __init__(self):
        sens = self._unpickle_doc()
        if sens:
            data = [doc2vec.LabeledSentence(words=words, tags=["SENT_%d" % i]) for i, words in enumerate(sens)]
            self._d2v = Doc2Vec(data, size=config.STATE_D2V_DIM, min_count=1)
        else:
            self._d2v = Doc2Vec(size=config.STATE_D2V_DIM, min_count=1)

    def _pickle_doc(self, tokens):
        # tokens.sort()
        tokens = tuple(tokens)
        # Save these tokens to file
        if os.path.exists(self.DOC2VEC_DATA):
            with open(self.DOC2VEC_DATA, 'rb') as f:
                pickled_data = pickle.load(f)
        else:
            pickled_data = set()
        pickled_data.add(tokens)
        with open(self.DOC2VEC_DATA, 'wb') as f:
            pickle.dump(pickled_data, f)

    def _unpickle_doc(self):
        data = None
        if os.path.exists(self.DOC2VEC_DATA):
            with open(self.DOC2VEC_DATA, 'rb') as f:
                try:
                    data = pickle.load(f)
                except EOFError:
                    pass
        return(data)

    @staticmethod
    def _get_words(phrase):
        phrase = phrase.lower()
        t = parsetree(phrase)
        words = []
        for s in t:
            for chunk in s.chunks:
                if chunk.type == 'NP':
                    for w in chunk.words:
                        if w.type == "CD":
                            try:
                                int(w.string)
                                words.append(w.string)
                            except ValueError:
                                try:
                                    words.append(text2num.text2num(w.string))
                                except text2num.NumberException:
                                    pass
                        elif w.type == "NN":
                            words.append(w.string.lower())
        return([unicode(w) for w in words])

    def calculate(self, placeholders):
        tokens = [] # [i.lower() for i in placeholders]
        for p in placeholders:
            tokens += self._get_words(p)
        self._pickle_doc(tokens)
        try: # If no samples are trained
            vector = self._d2v.infer_vector(tokens)
            logging.debug("%s ---> %s ---> %s" % (str(placeholders), str(tokens), str(vector)))
        except AttributeError:
            logging.debug("Attribute error when infering Doc2Vec vector")
            vector = None
        return(vector)

    def close(self):
        # Save D2V docs for next time training
        self._d2v.save(self.DOC2VEC_MODEL)
