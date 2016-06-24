import json
import numpy as np

from gensim.models import Word2Vec
from sklearn.decomposition import IncrementalPCA
# from bhtsne import tsne

WORD2VEC_MODEL = 'GNews.model'
WORD2VEC_JSON = 'word2vec.json'

model = Word2Vec.load(WORD2VEC_MODEL)

words = []
vectors = np.empty((len(model.vocab.keys()), 300))
# vectors = np.empty((6, 300))

# for i, w in enumerate(['email', 'password', 'user', 'date', 'this', 'is']):
for i, w in enumerate(model.vocab.keys()):
    words.append(w)
    vectors[i] = model[w]

# vectors = tsne(vectors, dimensions=3, perplexity=50)
ipca = IncrementalPCA(n_components=2, batch_size=25000)
vectors = ipca.fit_transform(vectors)

json_vectors = {}
for i, w in enumerate(words):
    json_vectors[w] = vectors[i].tolist()

with open(WORD2VEC_JSON, 'w') as f:
    json.dump(json_vectors, f)
