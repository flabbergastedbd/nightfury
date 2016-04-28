import os
import theano
import lasagne
import numpy as np
import cPickle as pickle

from theano import tensor as T

def get_batch(batch_size):
    inputs = [[i] for i in np.random.randint(0, high=100000, size=batch_size)]
    targets = [inputs[i][0] % 10 for i in range(0, batch_size)]
    return(inputs, targets)

filename = "baruvulu"

input_var = T.imatrix('inputs')
target_var = T.ivector('targets')

l1 = lasagne.layers.InputLayer(shape=(None, 1), input_var=input_var)
l2 = lasagne.layers.DropoutLayer(l1, p=0.2)
l3 = lasagne.layers.DenseLayer(l2, num_units=10, nonlinearity=lasagne.nonlinearities.sigmoid)
l4 = lasagne.layers.DropoutLayer(l3, p=0.5)
l5 = lasagne.layers.DenseLayer(l4, num_units=10, nonlinearity=lasagne.nonlinearities.sigmoid)

prediction = lasagne.layers.get_output(l5)
loss = lasagne.objectives.categorical_crossentropy(prediction, target_var).mean()

params = lasagne.layers.get_all_params(l5, trainable=True)
updates = lasagne.updates.nesterov_momentum(loss, params, learning_rate=0.01)

train_fn = theano.function([input_var, target_var], loss, updates=updates)

test_prediction = lasagne.layers.get_output(l5, deterministic=True)
test_loss = lasagne.objectives.categorical_crossentropy(test_prediction, target_var).mean()
test_acc = T.mean(T.eq(T.argmax(test_prediction, axis=1), target_var), dtype=theano.config.floatX)

test_fn = theano.function([input_var, target_var], [test_loss, test_acc])

if os.path.exists(filename):
    with open(filename, "rb") as f:
        data = pickle.load(f)
        lasagne.layers.set_all_param_values(l5, data)

for i in range(0, 500):
    inputs, targets = get_batch(10000)
    loss = train_fn(inputs, targets)
    if i % 100 == 0: print(loss)

for i in range(0, 10):
    inputs, targets = get_batch(1)
    loss, acc = test_fn(inputs, targets)
    print(loss)
    print(acc)
    print("\n")

with open(filename, "wb") as f:
    pickle.dump(lasagne.layers.get_all_param_values(l5), f)
