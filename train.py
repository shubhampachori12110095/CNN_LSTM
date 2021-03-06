# -*- coding:utf8 -*-

'''
Single model may achieve LB scores at around 0.29+ ~ 0.30+
Average ensembles can easily get 0.28+ or less
Don't need to be an expert of feature engineering
All you need is a GPU!!!!!!!

The code is tested on Keras 2.0.0 using Tensorflow backend, and Python 2.7
'''

########################################
## import packages
########################################
import os
import sys
import re
import csv
import codecs
import numpy as np
import pandas as pd
import time

from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
from string import punctuation
from gensim.models import KeyedVectors
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.models import Model
from keras.callbacks import EarlyStopping, ModelCheckpoint

from config import BASE_DIR, EMBEDDING_FILE, TRAIN_DATA_FILE, DEV_DATA_FILE, TEST_DATA_FILE, MAX_SEQUENCE_LENGTH, MAX_NB_WORDS, EMBEDDING_DIM, VALIDATION_SPLIT, STAMP
from config import num_rnn, num_dense, rate_drop_rnn, rate_drop_dense, act, re_weight
# from config import word2vec
from config import text_to_wordlist
from model import *

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

if __name__ == '__main__':
    texts_1 = [] 
    texts_2 = []
    labels = []
    with codecs.open(TRAIN_DATA_FILE, encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=',')
        header = next(reader)
        for values in reader:
            texts_1.append(text_to_wordlist(values[3], False, False))
            texts_2.append(text_to_wordlist(values[4], False, False))
            labels.append(int(values[5]))
            # break
    print('Found %s texts in train.csv' % len(texts_1))

    # dev_texts_1 = []
    # dev_texts_2 = []
    # dev_labels = []
    # with codecs.open(DEV_DATA_FILE, encoding='utf-8') as f:
    #     reader = csv.reader(f, delimiter=',')
    #     header = next(reader)
    #     for values in reader:
    #         dev_texts_1.append(text_to_wordlist(values[3], False, False))
    #         dev_texts_2.append(text_to_wordlist(values[4], False, False))
    #         dev_labels.append(int(values[5]))
    #         # break
    # print('Found %s texts in dev.csv' % len(dev_texts_1))

    # test_texts_1 = []
    # test_texts_2 = []
    # test_labels = []
    # with codecs.open(TEST_DATA_FILE, encoding='utf-8') as f:
    #     reader = csv.reader(f, delimiter=',')
    #     header = next(reader)
    #     for values in reader:
    #         test_texts_1.append(text_to_wordlist(values[3], False, False))
    #         test_texts_2.append(text_to_wordlist(values[4], False, False))
    #         test_labels.append(int(values[5]))
    #         # break
    # print('Found %s texts in test.csv' % len(test_texts_1))

    # test_texts_1 = []
    # test_texts_2 = []
    # test_ids = []
    # with codecs.open(TEST_DATA_FILE, encoding='utf-8') as f:
    #     reader = csv.reader(f, delimiter=',')
    #     header = next(reader)
    #     for values in reader:
    #         test_texts_1.append(text_to_wordlist(values[1], False, False))
    #         test_texts_2.append(text_to_wordlist(values[2], False, False))
    #         test_ids.append(values[0])
    #         # break
    # print('Found %s texts in test.csv' % len(test_texts_1))

    tokenizer = Tokenizer(num_words=MAX_NB_WORDS)
    tokenizer.fit_on_texts(texts_1 + texts_2)
    # tokenizer.fit_on_texts(texts_1 + texts_2 + test_texts_1 + test_texts_2)

    sequences_1 = tokenizer.texts_to_sequences(texts_1)
    sequences_2 = tokenizer.texts_to_sequences(texts_2)
    # test_sequences_1 = tokenizer.texts_to_sequences(test_texts_1)
    # test_sequences_2 = tokenizer.texts_to_sequences(test_texts_2)

    word_index = tokenizer.word_index
    print('Found %s unique tokens' % len(word_index))

    data_1 = pad_sequences(sequences_1, maxlen=MAX_SEQUENCE_LENGTH)
    data_2 = pad_sequences(sequences_2, maxlen=MAX_SEQUENCE_LENGTH)
    labels = np.array(labels)
    print('Shape of data tensor:', data_1.shape)
    print('Shape of label tensor:', labels.shape)

    ########################################
    ## prepare embeddings
    ########################################
    print('Preparing embedding matrix')

    nb_words = min(MAX_NB_WORDS, len(word_index))+1

    # embedding_matrix = np.zeros((nb_words, EMBEDDING_DIM))
    numpy_rng = np.random.RandomState(4321)
    embedding_matrix = numpy_rng.uniform(low=-0.05, high=0.05, size=(nb_words, EMBEDDING_DIM))
    embeddings_from_file = {}
    with codecs.open(EMBEDDING_FILE) as embedding_file:
        for line in embedding_file.readlines():
            fields = line.strip().split(' ')
            word = fields[0]
            vector = np.array(fields[1:], dtype='float32')
            embeddings_from_file[word] = vector
    
    count = 0    
    for word, i in word_index.items():
        if word in embeddings_from_file:
            embedding_matrix[i] = embeddings_from_file[word]
            count += 1
    print('Null word embeddings: %d' % (nb_words-count))
    print('######################################################')


    # for word, i in word_index.items():
    #     if word in word2vec.vocab:
    #         embedding_matrix[i] = word2vec.word_vec(word)
    # print('Null word embeddings: %d' % np.sum(np.sum(embedding_matrix, axis=1) == 0))

    ########################################
    ## sample train/validation data
    ########################################
    np.random.seed(1234)
    perm = np.random.permutation(len(data_1))
    idx_train = perm[:int(len(data_1)*(1-VALIDATION_SPLIT))]
    idx_dev = perm[int(len(data_1)*(1-VALIDATION_SPLIT)):int(len(data_1)*(1-VALIDATION_SPLIT/2))]
    idx_test = perm[int(len(data_1)*(1-VALIDATION_SPLIT/2)):]
    # idx_val = perm[int(len(data_1)*(1-VALIDATION_SPLIT)):]

    data_1_train = np.vstack((data_1[idx_train], data_2[idx_train]))
    data_2_train = np.vstack((data_2[idx_train], data_1[idx_train]))
    labels_train = np.concatenate((labels[idx_train], labels[idx_train]))

    data_1_dev = np.vstack((data_1[idx_dev], data_2[idx_dev]))
    data_2_dev = np.vstack((data_2[idx_dev], data_1[idx_dev]))
    labels_dev = np.concatenate((labels[idx_dev], labels[idx_dev]))
    
    data_1_test = np.vstack((data_1[idx_test], data_2[idx_test]))
    data_2_test = np.vstack((data_2[idx_test], data_1[idx_test]))
    labels_test = np.concatenate((labels[idx_test], labels[idx_test]))
    
    # data_1_val = np.vstack((data_1[idx_val], data_2[idx_val]))
    # data_2_val = np.vstack((data_2[idx_val], data_1[idx_val]))
    # labels_val = np.concatenate((labels[idx_val], labels[idx_val]))

    weight_val = np.ones(len(labels_dev))
    if re_weight:
        weight_val *= 0.472001959
        weight_val[labels_dev==0] = 1.309028344

    ########################################
    ## define the model structure
    ########################################

    if sys.argv[1] == '0':
        model = basic_baseline(nb_words, EMBEDDING_DIM, \
                               embedding_matrix, MAX_SEQUENCE_LENGTH, \
                               num_rnn, num_dense, rate_drop_rnn, \
                               rate_drop_dense, act)
        model_name = 'basic_baseline'

    elif sys.argv[1] == '1':
        model = basic_attention(nb_words, EMBEDDING_DIM, \
                                embedding_matrix, MAX_SEQUENCE_LENGTH, \
                                num_rnn, num_dense, rate_drop_rnn, \
                                rate_drop_dense, act)
        model_name = 'basic_attention'
    
    elif sys.argv[1] == '2':
        model = cnn_rnn(nb_words, EMBEDDING_DIM, \
                        embedding_matrix, MAX_SEQUENCE_LENGTH, \
                        num_rnn, num_dense, rate_drop_rnn, \
                        rate_drop_dense, act)
        model_name = 'cnn_rnn'

    elif sys.argv[1] == '3':
        model = cnn_rnn_tmp(nb_words, EMBEDDING_DIM, \
                            embedding_matrix, MAX_SEQUENCE_LENGTH, \
                            num_rnn, num_dense, rate_drop_rnn, \
                            rate_drop_dense, act)
        model_name = 'cnn_rnn_tmp'

    elif sys.argv[1] == '4':
        model = basic_cnn(nb_words, EMBEDDING_DIM, \
                            embedding_matrix, MAX_SEQUENCE_LENGTH, \
                            num_rnn, num_dense, rate_drop_rnn, \
                            rate_drop_dense, act)
        model_name = 'basic_cnn'

    elif sys.argv[1] == '5':
        model = cnn_rnn_add(nb_words, EMBEDDING_DIM, \
                            embedding_matrix, MAX_SEQUENCE_LENGTH, \
                            num_rnn, num_dense, rate_drop_rnn, \
                            rate_drop_dense, act)
        model_name = 'cnn_rnn_add'

    else:
        print("what the fuck!")
    
    early_stopping =EarlyStopping(monitor='val_acc', patience=3)
    # early_stopping =EarlyStopping(monitor='val_loss', patience=3)
    now_time = '_'.join(time.asctime(time.localtime(time.time())).split(' '))
    bst_model_path = './models/' + model_name + STAMP + '_' + now_time + '.h5'
    print('bst_model_path:', bst_model_path)
    model_checkpoint = ModelCheckpoint(bst_model_path, monitor='val_loss', save_best_only=True, save_weights_only=True)

    if os.path.exists(bst_model_path):
        model.load_weights(bst_model_path)

    ########################################
    ## add class weight
    ########################################
    if re_weight:
        class_weight = {0: 1.309028344, 1: 0.472001959}
    else:
        class_weight = None

    hist = model.fit([data_1_train, data_2_train], labels_train, 
                     validation_data=([data_1_dev, data_2_dev], labels_dev, weight_val), 
                     epochs=200, batch_size=128, shuffle=True, 
                     class_weight=class_weight, callbacks=[early_stopping, model_checkpoint])
                     # class_weight=class_weight, callbacks=[model_checkpoint])
    
    # model.load_weights(bst_model_path)
    print('min_val_loss:', min(hist.history['val_loss']))
    print('bst_model_path:', bst_model_path)
    print('test:', model.evaluate([data_1_test, data_2_test], labels_test, batch_size=512))
