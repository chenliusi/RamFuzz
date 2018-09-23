#!/usr/bin/env python

# Copyright 2016-2018 The RamFuzz contributors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A sample Keras model trainable on a set of fuzzlogs.  The model is adapted
from Alexander Rakhlin's sample implementation of NLP CNN:
https://github.com/alexander-rakhlin/CNN-for-Sentence-Classification-in-Keras.

Usage: $0 [epochs] [batch_size]
Defaults: epochs=1, batch_size=50

Expects a train/ subdirectory containing fuzzlogs whose filenames indicate
whether the run was a success or failure.  Filenames ending in `.0` are success
fuzzlogs, while all other files are failure fuzzlogs.  (This makes it easy to
generate fuzzlogs via shell commands like `./runtest; mv fuzzlog
train/$((counter++)).$?`.)

"""

from keras.constraints import min_max_norm
from keras.layers import BatchNormalization, Dense, Dropout, Conv1D
from keras.layers import Embedding, Flatten, Input, MaxPooling1D
from keras.layers.merge import concatenate
from keras.metrics import binary_crossentropy
from keras.models import Model
from keras.optimizers import Adam
import glob
import keras.backend as K
import numpy as np
import os.path
import rfutils
import sys

sys.setrecursionlimit(9999)

exetree = rfutils.node()
files = glob.glob(os.path.join('train', '*'))
for f in files:
    exetree.add(rfutils.open_and_logparse(f), f.endswith('.0'))

poscount = exetree.depth()
locidx = exetree.locidx()

K.set_floatx('float64')


def get_training_data(tree_root, poscount, locidx):
    """Builds input data from a files list."""
    locs = []  # One element per node; each is a list of location indexes.
    vals = []  # One element per node; each is a parallel list of values.
    labels = []  # One element per node: true iff node.reaches_success.
    for n in tree_root.preorder_dfs():
        flocs = np.zeros(poscount, np.uint64)
        fvals = np.zeros((poscount, 1), np.float64)
        for p, (v, l) in enumerate(n.logseq()):
            idx = locidx.get_index(l)
            if idx:
                flocs[p] = idx
                fvals[p] = v
        locs.append(flocs)
        vals.append(fvals)
        labels.append(n.reaches_success)
    return np.array(locs), np.array(vals), np.array(labels)


locs, vals, labels = get_training_data(exetree, poscount, locidx)

embedding_dim = 4
filter_sizes = (3, 8)
num_filters = 1
dropout_prob = (0.01, 0.01)
hidden_dims = 10

in_vals = Input((poscount, 1), name='vals', dtype='float64')
normd = BatchNormalization(
    axis=1, gamma_constraint=min_max_norm(),
    beta_constraint=min_max_norm())(in_vals)
in_locs = Input((poscount, ), name='locs', dtype='uint64')
embed_locs = Embedding(
    locidx.watermark, embedding_dim, input_length=poscount)(in_locs)
merged = concatenate([embed_locs, normd])
drop = Dropout(dropout_prob[0])(merged)
conv_list = []
for filtsz in filter_sizes:
    tmp = Conv1D(num_filters, filtsz, activation='relu')(drop)
    tmp = Flatten()(MaxPooling1D()(tmp))
    conv_list.append(tmp)
out = Dense(
    1, activation='sigmoid')(Dense(hidden_dims, activation='relu')(Dropout(
        dropout_prob[1])(concatenate(conv_list))))
ml = Model(inputs=[in_locs, in_vals], outputs=out)
ml.compile(Adam(lr=0.01), metrics=['acc'], loss=binary_crossentropy)


def fit(eps, bsz):
    ml.fit([locs, vals], labels, batch_size=bsz, epochs=eps)


def validate(valn_files):
    """Validates ml against valn_files, a list of log file names.

    Returns indices of correct predictions.

    """
    locsv, valsv, labelsv = rfutils.read_data(valn_files, poscount, locidx)
    pred = ml.predict([locsv, valsv])[:, 0]
    return ((pred > 0.7) == labelsv).nonzero()[0]


def corrfrac(filelist):
    """Invokes validate() on the given list of file names.

    Returns the fraction of correct predictions.

    """
    return float(len(validate(filelist))) / len(filelist)


def layerfun(i):
    """Returns a backend function calculating the output of i-th layer."""
    return K.function(
        [ml.layers[0].input, ml.layers[1].input,
         K.learning_phase()], [ml.layers[i].output])


def layer_output(l, i):
    """Returns the output of layer l on input i."""
    return layerfun(l)([locs[i:i + 1], vals[i:i + 1], 0])[0]


def convo(layer, input, i):
    """Convolves the Conv1D layer's weights with input at position i."""
    wts = layer.get_weights()[0][::-1]
    bias = layer.get_weights()[1]
    return np.sum([np.dot(input[i + j], w) for j, w in enumerate(wts)]) + bias


def convo_elements(layer_input, weights, offset):
    """Prints individual convolution elements at given offset.

    Returns their sum.

    """
    sum = 0
    for i in range(0, 8):
        e = np.dot(weights[i], layer_input[0, offset + i])
        print ' %20.18f #o%dw%d' % (e, offset + i, i)
        sum += e
    return sum


fit(
    eps=int(sys.argv[1]) if len(sys.argv) > 1 else 1,
    # Large batches tend to cause NaNs in batch normalization.
    bsz=int(sys.argv[2]) if len(sys.argv) > 2 else 50)

glval = glob.glob(os.path.join('valn', '*.[sf]'))
if glval:
    print 'Validation: ', corrfrac(glval)