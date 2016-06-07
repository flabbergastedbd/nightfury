import os
import json
import shutil
import text2num
import logging
import tensorflow as tf
import numpy as np
import logging
import cPickle as pickle

from pattern.en import parsetree, pprint, singularize, wordnet
from gensim.models import Word2Vec, word2vec, Doc2Vec, doc2vec
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import Table, Column, Integer, String, Boolean,\
            Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from selenium.common.exceptions import InvalidSelectorException, NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys


Base = declarative_base()

class Word2Vec(Base):
    __tablename__ = "dom_states"
    word = Column(String, primary_key=True)
    vector_string = Column(Text)

    @hybrid_property
    def vector(self):
        return(json.loads(self.vector_string))

    def __str__(self):
        return("Word: %s (%s)" % (self.word, self.value))


class NAgent(object):
    WORD2VEC_DB = 'word2vec.db'
    WORD2VEC_JSON = 'word2vec.json'
    DOC2VEC_MODEL = 'doc2vec.model'
    DOC2VEC_DATA = 'doc2vec.pickle'
    def __init__(self, alpha=0.1, gamma=0.9, epsilon=0.3, constant_scaling=0.7, n_state_dims=35, n_actions=10):
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.constant_scaling = constant_scaling
        self.n_state_dims = n_state_dims
        self.n_actions = n_actions
        self.experiences = []
        self.__init_sqlalchemy_session()
        self.__init_nn()
        self._load_d2v()

    def __init_nn(self):
        self.nn = NeuralNetwork(self.n_state_dims, 40, 40, self.n_actions)

    def __init_sqlalchemy_session(self):
        self.engine = create_engine("sqlite:///" + self.WORD2VEC_DB)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.scoped_factory = scoped_session(self.session_factory)
        self.session = self.scoped_factory()
        if self.session.query(Word2Vec).count() == 0: self._load_w2v()

    def _load_w2v(self):
        with open(self.WORD2VEC_JSON, 'r') as f:
            w_json = json.load(f)
            for word, vector in w_json.iteritems():
                self.session.add(Word2Vec(word=word, vector_string=json.dumps(vector)))
        self.session.commit()

    def _load_d2v(self):
        sens = self._unpickle_doc()
        data = [doc2vec.LabeledSentence(words=words, tags=["SENT_%d" % i]) for i, words in enumerate(sens)]
        if sens:
            self._d2v = Doc2Vec(data, size=5, min_count=1)
        else:
            self._d2v = Doc2Vec(size=5, min_count=1)

    @staticmethod
    def _get_words(phrase):
        phrase = phrase.lower()
        t = parsetree(phrase)
        words = []
        for s in t:
            for chunk in s.chunks:
                if chunk.type == 'NP':
                    for word in chunk.words:
                        if word.type == "CD":
                            try:
                                int(w.string)
                                words.append(w.string)
                            except ValueError:
                                try:
                                    words.append(text2num.text2num(w.string))
                                except text2num.NumberException:
                                    pass
                        elif word.type == "NN":
                            words.append(word.string.lower())
        return(words)

    def w2v(self, phrase):
        words = self._get_words(phrase)
        vector = [0.0, 0.0, 0.0]
        logging.debug("[*] %s --> %s" % (phrase, str(words)))
        if words:
            vec_objs = self.session.query(Word2Vec).filter(Word2Vec.word.in_(words)).all()
            for obj in vec_objs:
                vector = np.add(vector, obj.vector)
            logging.debug("[*] Vector averged by %d" % (len(vec_objs)))
            if len(vec_objs): vector = np.divide(vector, len(vec_objs))
        return(vector)

    def _pickle_doc(self, tokens):
        tokens.sort()
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

    def d2v(self, phrases):
        tokens = []
        for phrase in phrases:
            tokens += self._get_words(phrase)
        self._pickle_doc(tokens)
        return(self._d2v.infer_vector(tokens))

    def interact(self, state_vector, execute_action_on, i=None):
        adv_values = self.nn.predict([state_vector])[0]
        if np.random.random_sample() < self.e:
            i = np.argmax(adv_values)
        else:
            i = np.random.choice(range(0, len(actions)))
        action = actions[i]
        reward, new_state_vector = execute_action_on(action)
        new_adv_values = self.nn.predict([new_state_vector])[0]
        td_error = self.__td_error(
            adv_values[action],
            np.amax(adv_values),
            reward,
            np.amax(new_adv_values)
        )
        adv_values[actions.index(action)] += td_error
        self.nn.train([state_vector], [adv_values])
        for i, e in enumerate(self.experiences):
            if td_error < e[-1]:
                break
            elif i == len(self.experiences) - 1:
                i += 1
                break
        self.experiences.insert(i, [state_vector, action, reward, new_state_vector, td_error])

    def __td_error(self, a, max_a, reward, max_new_a):
        return(max_a + ((reward + self.gamma*max_new_a - max_a)/self.constant_scaling) - a)

    def replay(self):
        """
        This is prioritized replay using td error
        """
        e = self.experiences.pop()
        self.interact(e[0], lambda x: (e[2], e[3]), i=e[1])

    def close(self):
        self._d2v.save(self.DOC2VEC_MODEL)
        self.nn.close()


class NeuralNetwork(object):
    NN_MODEL = 'NN.model'
    def __init__(self, n_state_dims, n_hidden_1, n_hidden_2, n_actions):
        logging.debug("Creating neural network with following architecture")
        logging.debug("Input Vector Length: %d" % (n_state_dims))
        logging.debug("Hidden Layer 1 Length: %d" % (n_hidden_1))
        logging.debug("Hidden Layer 2 Length: %d" % (n_hidden_2))
        logging.debug("Actions Length: %d" % (n_actions))
        weights = {
            'h1': tf.Variable(tf.random_normal([n_state_dims, n_hidden_1])),
            'h2': tf.Variable(tf.random_normal([n_hidden_1, n_hidden_2])),
            'out': tf.Variable(tf.random_normal([n_hidden_2, n_actions]))
        }
        biases = {
            'h1': tf.Variable(tf.random_normal([n_hidden_1])),
            'h2': tf.Variable(tf.random_normal([n_hidden_2])),
            'out': tf.Variable(tf.random_normal([n_actions]))
        }
        self.x = tf.placeholder(tf.float32, [None, n_state_dims])
        self.y = tf.placeholder(tf.float32, [None, n_actions])

        self.predictor = self.__build_mlp(self.x, weights, biases)
        cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(self.predictor, self.y))
        self.optimizer = tf.train.AdamOptimizer(learning_rate=0.01).minimize(cost)
        self.saver = tf.train.Saver()
        self.__init_sess()

    def __init_sess(self):
        self.sess = tf.Session()
        if not os.path.exists(self.NN_MODEL):
            init = tf.initialize_all_variables()
            self.sess.run(init)
        else:
            shutil.copy2(self.NN_MODEL, self.NN_MODEL + '.backup')
            self.saver.restore(self.sess, self.NN_MODEL)

    def __close_sess(self):
        self.saver.save(self.sess, self.NN_MODEL)
        self.sess.close()

    def __build_mlp(self, _x, _weights, _biases):
        layer_1 = tf.nn.sigmoid(tf.add(tf.matmul(_x, _weights['h1']), _biases['h1']))
        layer_2 = tf.nn.sigmoid(tf.add(tf.matmul(layer_1, _weights['h2']), _biases['h2']))
        return(tf.matmul(layer_2, _weights['out']) + _biases['out'])

    def train(self, _x, _y):
        self.sess.run(self.optimizer, feed_dict={self.x: _x, self.y: _y})

    def predict(self, _x):
        predictions = self.sess.run(self.predictor, feed_dict={self.x: _x})
        return(predictions)

    def close(self):
        self.__close_sess()


if __name__ == "__main__":
    # agent = NAgent()
    # print(agent.w2v('profile'))
    nn = NeuralNetwork(2, 3, 3, 2)
    batch_size = 10000
    for j in range(0, 500):
        xs = 20 * np.random.random_sample(size=(batch_size, 2))
        ys = [[0, 0]] * batch_size
        for i in range(0, batch_size):
            ys[i] = [1, 0] if xs[i][0]**2 + xs[i][1]**2 <= 200 else [0, 1]
        if j != 499:
            nn.train(xs, ys)
        else:
            print(np.argmax(ys[-10:-1], axis=1))
            print(np.argmax(nn.predict(xs)[-10:-1], axis=1))
    nn.close()
