import os
import cPickle as pickle
import numpy as np

import tensorflow as tf

n_input = 10
n_hidden_1 = 20
n_hidden_2 = 20
n_classes = 10
epochs = 3000
batch_size = 100
save_file = '/tmp/model.cpkt'

def get_batch(batch_size, lower=0, upper=70000):
    inputs = [np.random.normal(size=10) for i in range(0, batch_size)]
    targets = np.zeros((batch_size, n_classes))
    return(inputs, targets)

def build_mlp(_x, _weights, _biases):
    layer_1 = tf.nn.sigmoid(tf.add(tf.matmul(_x, _weights['h1']), _biases['h1']))
    layer_2 = tf.nn.sigmoid(tf.add(tf.matmul(layer_1, _weights['h2']), _biases['h2']))
    return(tf.matmul(layer_2, _weights['out']) + _biases['out'])

weights = {
    'h1': tf.Variable(tf.random_normal([n_input, n_hidden_1])),
    'h2': tf.Variable(tf.random_normal([n_hidden_1, n_hidden_2])),
    'out': tf.Variable(tf.random_normal([n_hidden_2, n_classes]))
}

biases = {
    'h1': tf.Variable(tf.random_normal([n_hidden_1])),
    'h2': tf.Variable(tf.random_normal([n_hidden_2])),
    'out': tf.Variable(tf.random_normal([n_classes]))
}

x = tf.placeholder(tf.float32, [None, n_input])
y = tf.placeholder(tf.float32, [None, n_classes])

pred = build_mlp(x, weights, biases)

cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(pred, y))
optimizer = tf.train.AdamOptimizer(learning_rate=0.01).minimize(cost)

init = tf.initialize_all_variables()

saver = tf.train.Saver()

with tf.Session() as sess:
    if not os.path.exists(save_file):
        sess.run(init)
        for i in range(0, epochs):
                inputs, targets = get_batch(batch_size)
                sess.run(optimizer, feed_dict={x: inputs, y: targets})
                avg_cost = sess.run(cost, feed_dict={x: inputs, y: targets})/batch_size
                if i % 500 == 0:
                    print(avg_cost)
        saver.save(sess, save_file)
    else:
        saver.restore(sess, save_file)
    inputs, targets = get_batch(10, lower=70000, upper=100000)
    prediction = sess.run(pred, feed_dict={x: inputs, y: targets})
    print(inputs)
    print(np.argmax(targets, axis=1))
    print(np.argmax(prediction, axis=1))
    print('\n')
