#!/usr/bin/env python
# coding: utf-8
# this file is generated by jupyter and modified by tudou13 to fix some bugs.

# In[1]:


# get_ipython().magic(u'matplotlib inline')
import matplotlib.pyplot as plt
import tensorflow as tf
from keras.layers import Layer, Input, Dense, Dropout, Flatten, MaxPooling2D, Conv2D, Reshape, concatenate
from keras.backend import batch_flatten
from keras.models import Model
import numpy as np
import networkx as nx

print(tf.__version__)  # 1.7.0
print(tf.keras.__version__)  # 2.1.4-tf


# In[2]:


def first_s2v_iter(adjmat, prev_embeddings, theta2):
    sum_neighbor_rows = tf.einsum('aij,jk->aik', adjmat, prev_embeddings)
    return tf.nn.relu(sum_neighbor_rows * theta2)


def other_s2v_iter(adjmat, prev_embeddings, theta2):
    sum_neighbor_rows = tf.einsum('aij,ajk->aik', adjmat, prev_embeddings)
    return tf.nn.relu(sum_neighbor_rows * theta2)


def s2v_four_times(adjmat, initial_embeddings, theta2):
    curr_embed = first_s2v_iter(adjmat, initial_embeddings, theta2)
    for i in range(3):
        curr_embed = other_s2v_iter(adjmat, curr_embed, theta2)
    return curr_embed


# In[3]:


class S2VLayer(Layer):
    def __init__(self, embedding_dim, **kwargs):
        self.embedding_dim = embedding_dim
        super(S2VLayer, self).__init__(**kwargs)

    def build(self, input_shape):
        self.theta2 = self.add_weight(name='theta2', shape=tf.TensorShape([1, self.embedding_dim]),
                                      initializer='uniform', trainable=True)
        self.initial_embeddings = self.add_weight(name='init_theta',
                                                  shape=tf.TensorShape([input_shape[1], self.embedding_dim]),
                                                  initializer='ones', trainable=False)
        super(S2VLayer, self).build(input_shape)

    def call(self, adjmat):
        return s2v_four_times(adjmat, self.initial_embeddings, self.theta2)

    def compute_output_shape(self, input_shape):
        return tf.TensorShape([input_shape[0], input_shape[1], self.embedding_dim])


# In[4]:


class S2VGraph(object):
    def __init__(self, g, node_tags, label):
        self.num_nodes = len(node_tags)
        self.node_tags = node_tags
        self.label = label
        self.g = g
        x, y = zip(*g.edges())
        self.num_edges = len(x)
        self.edge_pairs = np.ndarray(shape=(self.num_edges, 2), dtype=np.int32)
        self.edge_pairs[:, 0] = x
        self.edge_pairs[:, 1] = y
        self.edge_pairs = self.edge_pairs.flatten()


# In[5]:


def load_data():
    print('loading data')

    g_list = []
    label_dict = {}
    feat_dict = {}
    fold = 1
    with open('./data/%s/%s.txt' % ('NCI1', 'NCI1'), 'r') as f:
        n_g = int(f.readline().strip())
        for i in range(n_g):
            row = f.readline().strip().split()
            n, l = [int(w) for w in row]
            if not l in label_dict:
                mapped = len(label_dict)
                label_dict[l] = mapped
            g = nx.Graph()
            node_tags = []
            n_edges = 0
            for j in range(n):
                g.add_node(j)
                row = f.readline().strip().split()
                row = [int(w) for w in row]
                if not row[0] in feat_dict:
                    mapped = len(feat_dict)
                    feat_dict[row[0]] = mapped
                node_tags.append(feat_dict[row[0]])

                n_edges += row[1]
                for k in range(2, len(row)):
                    g.add_edge(j, row[k])
            assert len(g.edges()) * 2 == n_edges
            assert len(g) == n
            g_list.append(S2VGraph(g, node_tags, l))
    for g in g_list:
        g.label = label_dict[g.label]
    print('# classes: %d' % len(label_dict))
    print('# node features: %d' % len(feat_dict))

    train_idxes = np.loadtxt('./data/%s/10fold_idx/train_idx-%d.txt' % ('NCI1', fold), dtype=np.int32).tolist()
    test_idxes = np.loadtxt('./data/%s/10fold_idx/test_idx-%d.txt' % ('NCI1', fold), dtype=np.int32).tolist()

    return [g_list[i] for i in train_idxes], [g_list[i] for i in test_idxes]


# In[6]:


graph_train, graph_test = load_data()

# In[7]:


graph_train_shortened = [g for g in graph_train if g.num_nodes <= 50]
graph_test_shortened = [g for g in graph_test if g.num_nodes <= 50]


# In[8]:


def adjmat(gr):
    return nx.adjacency_matrix(gr).toarray().astype('float32')


def zero_padded_adjmat(graph, size):
    unpadded = adjmat(graph)
    padded = np.zeros((size, size))
    padded[0:unpadded.shape[0], 0:unpadded.shape[1]] = unpadded
    padded = np.reshape(padded, (padded.shape[0], padded.shape[1], 1))
    return padded


# In[9]:


graph_train_adjmat = np.stack([zero_padded_adjmat(g.g, 50) for g in graph_train_shortened])
graph_train_labels = np.expand_dims(np.stack([g.label for g in graph_train_shortened]).astype('float32'), axis=1)

graph_test_adjmat = np.stack([zero_padded_adjmat(g.g, 50) for g in graph_test_shortened])
graph_test_labels = np.expand_dims(np.stack([g.label for g in graph_test_shortened]).astype('float32'), axis=1)


# In[10]:


# In[14]:


def s2v_model(input_size=50):
    input_im = Input(shape=(input_size, input_size, 1))
    squeezed = Reshape((input_size, input_size))(input_im)
    l1 = S2VLayer(32)(squeezed)
    l1 = Reshape((-1, 50 * 32))(l1)  # added by tudou13
    out = Flatten()(l1)
    print(out.shape)
    out = Dense(64, activation='relu')(out)
    out = Dense(1, activation='sigmoid')(out)
    model = Model(input_im, out)  # modified by tudou13
    return model


# tf.enable_eager_execution() #commented by tudou13

s2v = s2v_model()
s2v.compile(optimizer='adam', loss='binary_crossentropy')

# In[13]:


s2v.summary()

# In[16]:


s2v.fit(graph_train_adjmat, graph_train_labels, epochs=500, batch_size=1000, shuffle=True,
        validation_data=(graph_test_adjmat, graph_test_labels))

# In[18]:


print s2v.predict(graph_test_adjmat[0:1, :, :, :])

# In[20]:


graph_test_labels[0]

# In[ ]:
