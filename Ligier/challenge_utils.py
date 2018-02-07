import numpy as np
from keras.models import Sequential
from keras.layers import Dense, Conv2D, Flatten, MaxPooling2D
from keras.optimizers import Adam
from keras.models import load_model
from collections import deque
from skimage import transform, color


def process_screen(screen):
    return 255*transform.resize(color.rgb2gray(screen[:,:404,:]),(screen.shape[0]/4,101))

def createNetwork():
    # We use the same architecture as in the original paper
    deepQnet = Sequential()
    deepQnet.add(Conv2D(filters=16, kernel_size=(8,8), strides=4,
                        activation="relu", input_shape=(72,101,4)))
    deepQnet.add(Conv2D(filters=32, kernel_size=(4,4), strides=2,
                        activation="relu"))
    deepQnet.add(Flatten())
    deepQnet.add(Dense(units=256, activation="relu"))
    deepQnet.add(Dense(units=2, activation="linear"))
    # We use Adam with a lower learning rate 
    deepQnet.compile(optimizer=Adam(lr=1e-4), loss='mean_squared_error')
    print(deepQnet.summary())
    deepQnet.save('model.h5')    
    
    targetNet = load_model('model.h5')

    return deepQnet, targetNet

def epsilon(step):
    if step < 5e3:
        return 1
    elif step < 1e6:
        return (0.1 - 5e3*(1e-3-0.1)/(1e6-5e3)) + step * (1e-3-0.1)/(1e6-5e3)
    else:
        return 1e-3

def clip_reward(r):
    #rr=0
    rr = 0.1
    if r>0:
        rr=1
    if r<0:
        rr=-1
    return rr

def greedy_action(network, x):
    Q = network.predict(np.array([x]))
    return np.argmax(Q)

class MemoryBuffer:
    "An experience replay buffer using numpy arrays"
    def __init__(self, length, screen_shape, action_shape):
        self.length = length
        self.screen_shape = screen_shape
        self.action_shape = action_shape
        shape = (length,) + screen_shape
        self.screens_x = np.zeros(shape, dtype=np.uint8) # starting states
        self.screens_y = np.zeros(shape, dtype=np.uint8) # resulting states
        shape = (length,) + action_shape
        self.actions = np.zeros(shape, dtype=np.uint8) # actions 
        self.rewards = np.zeros((length,1), dtype=np.uint8) # rewards
        self.terminals = np.zeros((length,1), dtype=np.bool) # true if resulting state is terminal
        self.terminals[-1] = True
        self.index = 0 # points one position past the last inserted element
        self.size = 0 # current size of the buffer
    
    def append(self, screenx, a, r, screeny, d):
        self.screens_x[self.index] = screenx
        self.actions[self.index] = a
        self.rewards[self.index] = r
        self.screens_y[self.index] = screeny
        self.terminals[self.index] = d
        self.index = (self.index+1) % self.length
        self.size = np.min([self.size+1,self.length])

    def stacked_frames_x(self, index):
        im_deque = deque(maxlen=4)
        pos = index % self.length
        for i in range(4):
            im = self.screens_x[pos]
            im_deque.appendleft(im)
            test_pos = (pos-1) % self.length
            if self.terminals[test_pos] == False:
                pos = test_pos
        return np.stack(im_deque, axis=-1)

    def stacked_frames_y(self, index):
        im_deque = deque(maxlen=4)
        pos = index % self.length
        for i in range(4):
            im = self.screens_y[pos]
            im_deque.appendleft(im)
            test_pos = (pos-1) % self.length
            if self.terminals[test_pos] == False:
                pos = test_pos
        return np.stack(im_deque, axis=-1)

    def minibatch(self, size):
        indices = np.random.choice(self.size, size=size, replace=False)
        x = np.zeros((size,)+self.screen_shape+(4,))
        y = np.zeros((size,)+self.screen_shape+(4,))
        for i in range(size):
            x[i] = self.stacked_frames_x(indices[i])
            y[i] = self.stacked_frames_y(indices[i])
        return x, self.actions[indices], self.rewards[indices], y, self.terminals[indices]
