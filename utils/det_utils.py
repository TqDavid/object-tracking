from ctypes import *
import numpy as np
import math
import random
import time
import sys
import os
import cv2

class BOX(Structure):
    _fields_ = [("x", c_float),
                ("y", c_float),
                ("w", c_float),
                ("h", c_float)]

class IMAGE(Structure):
    _fields_ = [("w", c_int),
                ("h", c_int),
                ("c", c_int),
                ("data", POINTER(c_float))]

class METADATA(Structure):
    _fields_ = [("classes", c_int),
                ("names", POINTER(c_char_p))]

class FEATURE(Structure):
    _fields_ = [("size", c_int),
                ("feat", POINTER(c_float))]
'''
os.chdir('./darknet')
lib = CDLL("/home/maths/btech/mt1140589/workspace/object-tracking/darknet/libdarknet.so", RTLD_GLOBAL)

make_boxes = lib.make_boxes
make_boxes.argtypes = [c_void_p]
make_boxes.restype = POINTER(BOX)

free_ptrs = lib.free_ptrs
free_ptrs.argtypes = [POINTER(c_void_p), c_int]

num_boxes = lib.num_boxes
num_boxes.argtypes = [c_void_p]
num_boxes.restype = c_int

make_probs = lib.make_probs
make_probs.argtypes = [c_void_p]
make_probs.restype = POINTER(POINTER(c_float))

load_net = lib.load_network_p
load_net.argtypes = [c_char_p, c_char_p, c_int]
load_net.restype = c_void_p

free_image = lib.free_image
free_image.argtypes = [IMAGE]

load_meta = lib.get_metadata
lib.get_metadata.argtypes = [c_char_p]
lib.get_metadata.restype = METADATA

load_image = lib.load_image_color
load_image.argtypes = [c_char_p, c_int, c_int]
load_image.restype = IMAGE

network_detect = lib.network_detect
network_detect.argtypes = [c_void_p, IMAGE, c_float, c_float, c_float, POINTER(BOX), POINTER(POINTER(c_float))]

extract_feat = lib.network_extract_feat
extract_feat.argtypes = [c_void_p, c_int]
extract_feat.restype = FEATURE

global net
global meta
global net_dim

net_dim = 608
net = load_net("cfg/yolo.cfg", "yolo.weights", 0)
meta = load_meta("cfg/coco.data")
os.chdir('../')

def detect(net, meta, image, thresh=.5, hier_thresh=.5, nms=.45):
    im = load_image(image, 0, 0)
    boxes = make_boxes(net)
    probs = make_probs(net)
    num =   num_boxes(net)
    network_detect(net, im, thresh, hier_thresh, nms, boxes, probs)
    res = []
    for j in range(num):
        for i in range(meta.classes):
            if probs[j][i] > 0:
                res.append((meta.names[i], probs[j][i], (boxes[j].x, boxes[j].y, boxes[j].w, boxes[j].h)))
    res = sorted(res, key=lambda x: -x[1])
    free_image(im)
    free_ptrs(cast(probs, POINTER(c_void_p)), num)
    return res

def extract(net, n):
    f = extract_feat(net, n)
    feat = np.zeros((f.size))
    for j in range(f.size):
        feat[j] = f.feat[j]
    feat = feat.reshape((19,19,1024))
    return feat

def prepare_data(data_dirs = ['Human2','Human3','Human4','Human5','Human6','Human7','Human8','Human9','Woman','Jogging-1', 'Jogging-2','Walking','Walking2']):
    path_prefix = './data/TB-50/'
    frame_paths_dirs, frame_bboxs_dirs, frame_dim_dirs = [], [], []
    print "All Directories List:", data_dirs

    for data_dir in data_dirs:
        frame_paths, frame_bboxs, frame_width, frame_height = [], [], 0, 0
        print "Reading Directory:", data_dir.split('-')[0]

        groundtruth_path = path_prefix + data_dir + '/groundtruth_rect.txt'
        if data_dir=='Jogging-1':
            groundtruth_path = path_prefix + 'Jogging' + '/groundtruth_rect.1.txt'
        if data_dir=='Jogging-2':
            groundtruth_path = path_prefix + 'Jogging' + '/groundtruth_rect.2.txt'

        with open(groundtruth_path, 'rb') as f_handle:
            lines = f_handle.readlines()
            for i,line in enumerate(lines):
                frame_path = path_prefix + data_dir.split('-')[0] + '/img/' + str(i+1).zfill(4) + '.jpg'
                if i==0:
                    frame = cv2.imread(frame_path)
                    frame_height, frame_width, frame_channel = frame.shape[0], frame.shape[1], frame.shape[2]

                if data_dir=='Jogging-1' or data_dir=='Jogging-2' or data_dir=='Woman' or data_dir=='Walking' or data_dir=='Walking2':
                    frame_bbox = line.rstrip('\n').split()
                    frame_bboxs.append(frame_bbox)
                else:
                    frame_bbox = line.rstrip('\n').split(',')
                    frame_bboxs.append(frame_bbox)

                frame_paths.append(frame_path)

        print "Number of samples:", len(frame_paths)
        print "Done.."
        frame_paths_dirs.append(frame_paths)
        frame_bboxs_dirs.append(frame_bboxs)
        frame_dim_dirs.append([frame_height, frame_width, frame_channel])
    return frame_paths_dirs, frame_bboxs_dirs, frame_dim_dirs

def extract_spatio_info(frame_path):
    obj_detections = []
    out = detect(net, meta, frame_path)
    vis_feat = extract(net, 24)

    for detection in out:
        if detection[0]=='car' or detection[0]=='truck' or detection[0]=='person':
            obj_detections.append(detection)
    return obj_detections, vis_feat


def generate_heatmap_feat(det_x, det_y, det_h, det_w, smap=32):

    heatmap = np.zeros((smap, smap))
    scaled_x, scaled_y, scaled_h, scaled_w = int(det_x*smap), int(det_y*smap), int(det_h*smap), int(det_w*smap)
    heatmap[scaled_y:(scaled_y+scaled_h+1), scaled_x:(scaled_x+scaled_w+1)] = 1.0
    heatmap_feat = heatmap.reshape((-1))
    return heatmap_feat


def process_data(frame_paths_dirs, frame_bboxs_dirs, frame_dim_dirs, data_dirs = ['Human2','Human3','Human4','Human5','Human6','Human7','Human8','Human9','Woman','Jogging-1','Jogging-2','Walking','Walking2']):
    for i, (frame_paths, frame_bboxs, frame_dim) in enumerate(zip(frame_paths_dirs, frame_bboxs_dirs, frame_dim_dirs)):
        frame_height, frame_width = frame_dim[0], frame_dim[1]

        vis_data_file = './data/vis_feats_' + data_dirs[i]
        heatmap_data_file = './data/heatmap_feats_' + data_dirs[i]

        # if i<0:
        #     continue
        with open(vis_data_file, 'wb', 0) as f_vis, open(heatmap_data_file, 'wb', 0) as f_heat:
            print "Extracting features for Data in Directory:", data_dirs[i].split('-')[0]
            print "Begin.."
            start = time.time()
            for j, (frame_path, frame_bbox) in enumerate(zip(frame_paths,frame_bboxs)):

                # if j<0:
                #     continue
                if j%100==0 and j!=0:
                    end = time.time()
                    print "Frames Processed:", j, "| Time Taken:", (end-start)
                    start = end

                _, feat = extract_spatio_info(frame_path)
                feat_norm = np.amax(feat, axis=(0,1))

                det_x = float(frame_bbox[0])/frame_width
                det_y = float(frame_bbox[1])/frame_height
                det_h = float(frame_bbox[3])/frame_height
                det_w = float(frame_bbox[2])/frame_width

                heatmap_feat = generate_heatmap_feat(det_x, det_y, det_h, det_w)
                np.savetxt(f_vis, (feat_norm.reshape((1,-1))), delimiter=',')
                np.savetxt(f_heat, (heatmap_feat.reshape((1,-1))), delimiter=',')
'''

def read_data(sequence_length=6, vis_feat_size=1024, heatmap_feat_size=1024, data_dirs = ['Human2','Human3','Human4','Human5','Human6','Human7','Human8','Human9','Woman','Jogging-1','Jogging-2','Walking','Walking2']):
    for data_dir in data_dirs:

        print "Reading Directory:", data_dir
        vis_data_file = './data/vis_feats_' + data_dir
        heatmap_data_file = './data/heatmap_feats_' + data_dir

        vis_feat = np.genfromtxt(vis_data_file, dtype='float32', delimiter=',')
        heatmap_feat = np.genfromtxt(heatmap_data_file, dtype='float32', delimiter=',')

        leng = vis_feat.shape[0]
        x = np.zeros((leng - sequence_length, sequence_length, (vis_feat_size + heatmap_feat_size)))
        y = np.zeros((leng - sequence_length, sequence_length, heatmap_feat_size))

        for i in range(leng-sequence_length):

            x_sample = np.zeros((sequence_length, (vis_feat_size + heatmap_feat_size)))
            y_sample = np.zeros((sequence_length, heatmap_feat_size))
            for j in range(sequence_length):
                x_sample[j, :] = np.append(vis_feat[i+j], heatmap_feat[i+j])
                y_sample[j, :] = heatmap_feat[i+j+1]

            x[i] = x_sample
            y[i] = y_sample

        yield (x,y)
'''
def get_trainval_data(data_dirs = ['Human2','Human3','Human4','Human5','Human6','Human7','Human8','Human9','Woman','Jogging-1','Jogging-2','Walking','Walking2'], val_data_dirs=['Human3','Human8','Jogging-2','Walking2']):

    x_train = None
    y_train = None
    x_val = None
    y_val = None

    val_index = [data_dirs.index(data_dir) for data_dir in val_data_dirs]
    data_generator = read_data()
    for i,(x,y) in enumerate(data_generator):

        if i in val_index:
            if x_val==None and y_val==None:
                x_val = x
                y_val = y
            else:
                x_val = np.append(x_val, x, axis=0)
                y_val = np.append(y_val, y, axis=0)
        else:
            if x_train==None and y_train==None:
                x_train = x
                y_train = y
            else:
                x_train = np.append(x_train, x, axis=0)
                y_train = np.append(y_train, y, axis=0)

    print "Shapes of Train/Val X/Y Data:", x_train.shape, y_train.shape, x_val.shape, y_val.shape
    return x_train, y_train, x_val, y_val

def read_test_data(sequence_length=6, vis_feat_size=1024, heatmap_feat_size=1024, data_dirs = ['Human2','Human3','Human4','Human5','Human6','Human7','Human8','Human9','Woman','Jogging-1','Jogging-2','Walking','Walking2']):
    for data_dir in data_dirs:

        print "Reading Directory:", data_dir
        vis_data_file = './data/vis_feats_' + data_dir
        heatmap_data_file = './data/heatmap_feats_' + data_dir

        vis_feat = np.genfromtxt(vis_data_file, dtype='float32', delimiter=',')
        heatmap_feat = np.genfromtxt(heatmap_data_file, dtype='float32', delimiter=',')

        leng = vis_feat.shape[0]
        x = np.zeros((leng - sequence_length, sequence_length, (vis_feat_size + heatmap_feat_size)))
        y = np.zeros((leng - sequence_length, sequence_length, heatmap_feat_size))

        for i in range(leng-sequence_length):

            x_sample = np.zeros((sequence_length, (vis_feat_size + heatmap_feat_size)))
            y_sample = np.zeros((sequence_length, heatmap_feat_size))
            for j in range(sequence_length):
                x_sample[j, :] = np.append(vis_feat_size[i+j], heatmap_feat[i+j])
                y_sample[j, :] = heatmap_feat[i+j+1]

            x[i] = x_sample
            y[i] = y_sample

        yield (x,y)




'''

def get_test_data(data_dirs = ['Human2','Human3','Human4','Human5','Human6','Human7','Human8','Human9','Woman','Jogging-1','Jogging-2','Walking','Walking2'], val_data_dirs=['Human3','Human8','Jogging-2','Walking2']):

    x_test = None
    y_test = None
    data_generator = read_data(data_dirs=data_dirs)
    for i,(x,y) in enumerate(data_generator):

        if x_test==None and y_test==None:
            x_test = x
            y_test = y
        else:
            x_test = np.append(x_test, x, axis=0)
            y_test = np.append(y_test, y, axis=0)

    print "Shapes of Train/Val X/Y Data:", x_test.shape, y_test.shape
    return x_test, y_test
