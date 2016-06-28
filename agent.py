import os
import json
import math
import shutil
import text2num
import tensorflow as tf
import numpy as np
import logging
import cPickle as pickle

from collections import OrderedDict
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
    WORD2VEC_DB = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'word2vec.db')
    WORD2VEC_JSON = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'word2vec.json')
    DOC2VEC_MODEL = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'doc2vec.model')
    DOC2VEC_DATA = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'doc2vec.pickle')
    EXPERIENCES_DATA = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'experiences.pickle')
    def __init__(self, alpha=0.1, gamma=0.9, epsilon=0.3, constant_scaling=0.7, n_state_dims=35, n_actions=10, load_network=True):
        if load_network == True:
            self.alpha = alpha
            self.gamma = gamma
            self.epsilon = epsilon
            self.constant_scaling = constant_scaling
            self.n_state_dims = n_state_dims
            self.n_actions = n_actions
            self.__init_sqlalchemy_session()
            self.__init_nn()
            self.__init_experiences()
        else:
            self.nn = None
            self.experiences = None
        self._load_d2v()

    def __init_experiences(self):
        if os.path.exists(self.EXPERIENCES_DATA):
            with open(self.EXPERIENCES_DATA, 'rb') as f:
                self.experiences = pickle.load(f)
        else:
            self.experiences = OrderedDict()

    def __init_nn(self):
        hidden_dims = int(math.ceil(self.n_state_dims + self.n_state_dims/10))
        self.nn = NeuralNetwork(self.n_state_dims, hidden_dims, hidden_dims, self.n_actions)

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
        if sens:
            data = [doc2vec.LabeledSentence(words=words, tags=["SENT_%d" % i]) for i, words in enumerate(sens)]
            self._d2v = Doc2Vec(data, size=2, min_count=1)
        else:
            self._d2v = Doc2Vec(size=2, min_count=1)

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

    def w2v(self, phrase):
        words = self._get_words(phrase)
        vector = [0.0, 0.0]
        if words:
            vec_objs = self.session.query(Word2Vec).filter(Word2Vec.word.in_(words)).all()
            for obj in vec_objs:
                vector = np.add(vector, obj.vector)
            if len(vec_objs): vector = np.divide(vector, len(vec_objs))
        logging.debug("%s ---> %s ---> %s" % (phrase, str(words), str(vector)))
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

    def d2v(self, placeholders):
        tokens = []
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

    def get_action(self, state_vector, elements):
        adv_values = self.nn.predict([state_vector])[0]
        filtered_indexes = []
        filtered_adv_values = []
        filtered_exploratory_indexes = []
        for j, e in enumerate(elements):
            if e:
                filtered_indexes.append(j)
                filtered_adv_values.append(adv_values[j])
                if e.interacted == False:  # When exploration, preferance to untouched stuff
                    filtered_exploratory_indexes.append(j)
        if np.random.random_sample() < self.epsilon:
            logging.info("Selecting profitable action")
            i = filtered_indexes[np.argmax(filtered_adv_values)]
        else:
            if len(filtered_exploratory_indexes) > 0:
                logging.info("Selecting randomly from non interacted elements")
                i = np.random.choice(filtered_exploratory_indexes)
            else:
                logging.info("Selecting randomly from all elements since everything seems already interacted")
                i = np.random.choice(filtered_indexes)
        return(i)

    def integrate(self, state_vector, action, reward, new_state_vector):
        adv_values = self.nn.predict(np.array([state_vector]))[0]
        new_adv_values = self.nn.predict(np.array([new_state_vector]))[0]
        td_error = self.__td_error(
            adv_values[action],
            np.amax(adv_values),
            reward,
            np.amax(new_adv_values)
        )
        adv_values[action] += td_error
        self.nn.train(np.array([state_vector]), np.array([adv_values]))
        # Insert the experience at right place
        self.experiences[tuple([tuple(state_vector), action, reward, tuple(new_state_vector)])] = td_error
        self.experiences = OrderedDict(sorted(self.experiences.items(), key=lambda x: x[1]))
        return(td_error)

    def __td_error(self, a, max_a, reward, max_new_a):
        return(max_a + ((reward + self.gamma*max_new_a - max_a)/self.constant_scaling) - a)

    def replay(self):
        """
        This is prioritized replay using td error
        """
        # e = self.experiences.popitem()
        k = self.experiences.keys()
        i = np.random.randint(0, high=len(k))
        e = (k[i], self.experiences[k[i]])
        if e[1] > 0:
            new_td_error = self.integrate(*e[0])
            logging.debug("Replay changed td error from %f to %f" % (e[1], new_td_error))
        else:
            logging.debug("Skipping replay as TD Error <= 0")

    def close(self):
        if self.experiences:
            # Save experiences json
            with open(self.EXPERIENCES_DATA, 'wb') as f:
                pickle.dump(self.experiences, f)
        # Save D2V docs for next time training
        self._d2v.save(self.DOC2VEC_MODEL)
        # Close neural network so it saves it weights
        if self.nn: self.nn.close()


class NeuralNetwork(object):
    NN_MODEL = 'NN.model'
    def __init__(self, n_state_dims, n_hidden_1, n_hidden_2, n_actions):
        logging.debug("Creating neural network with following architecture")
        logging.debug("Input Vector Length: %d" % (n_state_dims))
        logging.debug("Hidden Layer 1 Length: %d" % (n_hidden_1))
        logging.debug("Hidden Layer 2 Length: %d" % (n_hidden_2))
        logging.debug("Actions Length: %d" % (n_actions))
        weights = {
            'h1': tf.Variable(tf.random_normal([n_state_dims, n_hidden_1], stddev=(1/math.sqrt(n_state_dims)))),
            'h2': tf.Variable(tf.random_normal([n_hidden_1, n_hidden_2], stddev=(1/math.sqrt(n_hidden_1)))),
            'out': tf.Variable(tf.random_normal([n_hidden_2, n_actions], stddev=(1/math.sqrt(n_hidden_2))))
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
        layer_1 = tf.nn.relu(tf.add(tf.matmul(_x, _weights['h1']), _biases['h1']))
        layer_2 = tf.nn.relu(tf.add(tf.matmul(layer_1, _weights['h2']), _biases['h2']))
        return(tf.matmul(layer_2, _weights['out']) + _biases['out'])

    def train(self, _x, _y):
        self.sess.run(self.optimizer, feed_dict={self.x: _x, self.y: _y})

    def predict(self, _x):
        predictions = self.sess.run(self.predictor, feed_dict={self.x: _x})
        return(predictions)

    def close(self):
        logging.debug("Closing and saving neural network model")
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
