import numpy as np
import tensorflow as tf
from keras import backend as K
from keras.layers.normalization import BatchNormalization
from keras.layers import Activation, Input, Embedding, LSTM, Dense, Dropout
from keras.callbacks import ModelCheckpoint, EarlyStopping
from keras.models import Model
from keras.layers.wrappers import TimeDistributed
from keras.preprocessing.sequence import pad_sequences

def get_model():

    lstm_units = 512
    sequence_length = 6
    feat_size = 5120 # 4096(img-feat) + 1024(heat-map)

    x_input = Input(shape=(sequence_length, feat_size), dtype='float32', name='img_heatmap_feat')
    x = LSTM(lstm_units, return_sequences=False, implementation=2, name='recurrent_layer')(x_input)
    output = TimeDistributed(Dense(4, activation='sigmoid'), name='location')(x)

    model = Model(inputs=x_input, outputs=output)
    model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
    model.summary()

def train(x_train, y_train):

    checkpointer = ModelCheckpoint(filepath='weights/weights.{epoch:02d}-{val_loss:.2f}.hdf5', verbose=1, save_best_only=True)
    earlystopper = EarlyStopping(monitor='val_loss', patience=15, verbose=1, mode='auto')
    model.fit(x_train, y_train, validation_split=0.2, batch_size=64, epochs=100, verbose=0, shuffle=True, callbacks=[checkpointer, earlystopper])