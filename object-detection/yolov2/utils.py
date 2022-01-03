# Copyright 2018,2019,2020,2021 Sony Corporation.
# Copyright 2021 Sony Group Corporation.
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


# This file was forked from https://github.com/marvis/pytorch-yolo2 ,
# licensed under the MIT License (see LICENSE.external for more details).


import time
import math
import numpy as np
import nnabla

import struct  # get_image_size
import imghdr  # get_image_size


def raise_info_thread(f):

    def decorated(*args, **kw):
        try:
            return f(*args, **kw)
        except:
            import sys
            import traceback
            raise sys.exc_info()[0](traceback.format_exc())
    return decorated


def sigmoid(x):
    return 1.0/(math.exp(-x)+1.)


def bbox_iou(box1, box2, x1y1x2y2=True):
    if x1y1x2y2:
        mx = min(box1[0], box2[0])
        Mx = max(box1[2], box2[2])
        my = min(box1[1], box2[1])
        My = max(box1[3], box2[3])
        w1 = box1[2] - box1[0]
        h1 = box1[3] - box1[1]
        w2 = box2[2] - box2[0]
        h2 = box2[3] - box2[1]
    else:
        mx = min(box1[0]-box1[2]/2.0, box2[0]-box2[2]/2.0)
        Mx = max(box1[0]+box1[2]/2.0, box2[0]+box2[2]/2.0)
        my = min(box1[1]-box1[3]/2.0, box2[1]-box2[3]/2.0)
        My = max(box1[1]+box1[3]/2.0, box2[1]+box2[3]/2.0)
        w1 = box1[2]
        h1 = box1[3]
        w2 = box2[2]
        h2 = box2[3]
    uw = Mx - mx
    uh = My - my
    cw = w1 + w2 - uw
    ch = h1 + h2 - uh
    carea = 0
    if cw <= 0 or ch <= 0:
        return 0.0

    area1 = w1 * h1
    area2 = w2 * h2
    carea = cw * ch
    uarea = area1 + area2 - carea
    return carea/uarea


def bbox_iou_numpy(box1, box2, x1y1x2y2=True):
    if x1y1x2y2:
        mx = np.min((box1[0], box2[0]))
        Mx = np.max((box1[2], box2[2]))
        my = np.min((box1[1], box2[1]))
        My = np.max((box1[3], box2[3]))
        w1 = box1[2] - box1[0]
        h1 = box1[3] - box1[1]
        w2 = box2[2] - box2[0]
        h2 = box2[3] - box2[1]
    else:
        mx = np.min((box1[0]-box1[2]/2.0, box2[0]-box2[2]/2.0))
        Mx = np.max((box1[0]+box1[2]/2.0, box2[0]+box2[2]/2.0))
        my = np.min((box1[1]-box1[3]/2.0, box2[1]-box2[3]/2.0))
        My = np.max((box1[1]+box1[3]/2.0, box2[1]+box2[3]/2.0))
        w1 = box1[2]
        h1 = box1[3]
        w2 = box2[2]
        h2 = box2[3]
    uw = Mx - mx
    uh = My - my
    cw = w1 + w2 - uw
    ch = h1 + h2 - uh
    carea = 0
    if cw <= 0 or ch <= 0:
        return 0.0

    area1 = w1 * h1
    area2 = w2 * h2
    carea = cw * ch
    uarea = area1 + area2 - carea
    return carea/uarea


def bbox_ious(boxes1, boxes2, x1y1x2y2=True):
    if x1y1x2y2:
        mx = np.minimum(boxes1[0], boxes2[0])
        Mx = np.maximum(boxes1[2], boxes2[2])
        my = np.minimum(boxes1[1], boxes2[1])
        My = np.maximum(boxes1[3], boxes2[3])
        w1 = boxes1[2] - boxes1[0]
        h1 = boxes1[3] - boxes1[1]
        w2 = boxes2[2] - boxes2[0]
        h2 = boxes2[3] - boxes2[1]
    else:
        mx = np.minimum(boxes1[0]-boxes1[2]/2.0, boxes2[0]-boxes2[2]/2.0)
        Mx = np.maximum(boxes1[0]+boxes1[2]/2.0, boxes2[0]+boxes2[2]/2.0)
        my = np.minimum(boxes1[1]-boxes1[3]/2.0, boxes2[1]-boxes2[3]/2.0)
        My = np.maximum(boxes1[1]+boxes1[3]/2.0, boxes2[1]+boxes2[3]/2.0)
        w1 = boxes1[2]
        h1 = boxes1[3]
        w2 = boxes2[2]
        h2 = boxes2[3]
    uw = Mx - mx
    uh = My - my
    cw = w1 + w2 - uw
    ch = h1 + h2 - uh
    mask = ((cw <= 0) + (ch <= 0) > 0)
    area1 = w1 * h1
    area2 = w2 * h2
    carea = cw * ch
    carea[mask] = 0
    uarea = area1 + area2 - carea
    return carea/uarea


def bbox_ious_numpy(boxes1, boxes2, x1y1x2y2=True):
    if x1y1x2y2:
        mx = np.minimum(boxes1[0], boxes2[0])
        Mx = np.maximum(boxes1[2], boxes2[2])
        my = np.minimum(boxes1[1], boxes2[1])
        My = np.maximum(boxes1[3], boxes2[3])
        w1 = boxes1[2] - boxes1[0]
        h1 = boxes1[3] - boxes1[1]
        w2 = boxes2[2] - boxes2[0]
        h2 = boxes2[3] - boxes2[1]
    else:
        mx = np.minimum(boxes1[0]-boxes1[2]/2.0, boxes2[0]-boxes2[2]/2.0)
        Mx = np.maximum(boxes1[0]+boxes1[2]/2.0, boxes2[0]+boxes2[2]/2.0)
        my = np.minimum(boxes1[1]-boxes1[3]/2.0, boxes2[1]-boxes2[3]/2.0)
        My = np.maximum(boxes1[1]+boxes1[3]/2.0, boxes2[1]+boxes2[3]/2.0)
        w1 = boxes1[2]
        h1 = boxes1[3]
        w2 = boxes2[2]
        h2 = boxes2[3]
    uw = Mx - mx
    uh = My - my
    cw = w1 + w2 - uw
    ch = h1 + h2 - uh
    mask = ((cw <= 0) + (ch <= 0) > 0)
    area1 = w1 * h1
    area2 = w2 * h2
    carea = cw * ch
    carea[mask] = 0
    uarea = area1 + area2 - carea
    return carea/uarea


def nms(boxes, nms_thresh):
    if len(boxes) == 0:
        return boxes

    det_confs = np.zeros(len(boxes))
    for i in range(len(boxes)):
        det_confs[i] = 1-boxes[i][4]

    sortIds, _ = zip(*sorted(enumerate(det_confs), key=lambda x: x[1]))
    out_boxes = []
    for i in range(len(boxes)):
        box_i = boxes[sortIds[i]]
        if box_i[4] > 0:
            out_boxes.append(box_i)
            for j in range(i+1, len(boxes)):
                box_j = boxes[sortIds[j]]
                if bbox_iou(box_i, box_j, x1y1x2y2=False) > nms_thresh:
                    box_j[4] = 0
    return out_boxes


def get_region_boxes(output, conf_thresh, num_classes, anchors, num_anchors, only_objectness=1, validation=False):
    anchor_step = len(anchors)//num_anchors
    if output.ndim == 3:
        output = output.reshape(-1)
    batch = output.shape[0]
    assert(output.shape[1] == (5+num_classes)*num_anchors)
    h = output.shape[2]
    w = output.shape[3]

    t0 = time.time()
    all_boxes = []
    output = output.reshape((batch*num_anchors, 5+num_classes, h*w)).transpose(
        (1, 0, 2)).reshape((5+num_classes, batch*num_anchors*h*w))

    grid_x = np.tile(np.tile(np.linspace(0, w-1, w), (h, 1)),
                     (batch*num_anchors, 1, 1)).reshape(batch*num_anchors*h*w)
    grid_y = np.tile(np.tile(np.linspace(0, h-1, h), (w, 1)).transpose(),
                     (batch*num_anchors, 1, 1)).reshape(batch*num_anchors*h*w)
    anchor_w = np.array(anchors).reshape((num_anchors, anchor_step))[:, 0:1]
    anchor_h = np.array(anchors).reshape((num_anchors, anchor_step))[:, 1:2]
    anchor_w = np.tile(np.tile(anchor_w, (batch, 1)),
                       (1, 1, h*w)).reshape(batch*num_anchors*h*w)
    anchor_h = np.tile(np.tile(anchor_h, (batch, 1)),
                       (1, 1, h*w)).reshape(batch*num_anchors*h*w)

    def npv2nnablav(x):
        v = nnabla.Variable(x.shape)
        v.d = x
        return v
    grid_x, grid_y, anchor_h, anchor_w = map(
        npv2nnablav, [grid_x, grid_y, anchor_h, anchor_w])

    output_v = nnabla.Variable(output.shape)
    output_v.d = output
    outputs = nnabla.functions.split(output_v)
    xs = nnabla.functions.sigmoid(outputs[0]) + grid_x
    ys = nnabla.functions.sigmoid(outputs[1]) + grid_y
    ws = nnabla.functions.exp(outputs[2]) * anchor_w
    hs = nnabla.functions.exp(outputs[3]) * anchor_h
    det_confs = nnabla.functions.sigmoid(outputs[4])

    cls = nnabla.functions.stack(*outputs[5:])
    cls = cls.reshape((batch*num_anchors, num_classes, h*w))
    cls = nnabla.functions.transpose(cls, [0, 2, 1]).reshape(
        (batch*num_anchors*h*w, num_classes))

    o = output[5:5+num_classes].transpose()
    v = nnabla.Variable(o.shape)
    v.d = o
    cls_confs = nnabla.functions.softmax(v)
    cls_confs.forward()

    def nnablav2np(v):
        v.forward()
        return v.d
    xs, ys, ws, hs, det_confs, cls_confs = map(
        nnablav2np, [xs, ys, ws, hs, det_confs, cls_confs])
    cls_max_confs = np.max(cls_confs, axis=1)
    cls_max_ids = np.argmax(cls_confs, axis=1)
    t1 = time.time()

    sz_hw = h*w
    sz_hwa = sz_hw*num_anchors

    if validation:
        cls_confs = cls_confs.reshape(-1, num_classes)
    t2 = time.time()
    for b in range(batch):
        boxes = []
        for cy in range(h):
            for cx in range(w):
                for i in range(num_anchors):
                    ind = b*sz_hwa + i*sz_hw + cy*w + cx
                    det_conf = det_confs[ind]
                    if only_objectness:
                        conf = det_confs[ind]
                    else:
                        conf = det_confs[ind] * cls_max_confs[ind]

                    if conf > conf_thresh:
                        bcx = xs[ind]
                        bcy = ys[ind]
                        bw = ws[ind]
                        bh = hs[ind]
                        cls_max_conf = cls_max_confs[ind]
                        cls_max_id = cls_max_ids[ind]
                        box = [bcx/w, bcy/h, bw/w, bh/h,
                               det_conf, cls_max_conf, cls_max_id]
                        if (not only_objectness) and validation:
                            for c in range(num_classes):
                                tmp_conf = cls_confs[ind][c]
                                if c != cls_max_id and det_confs[ind]*tmp_conf > conf_thresh:
                                    box.append(tmp_conf)
                                    box.append(c)
                        boxes.append(box)
        all_boxes.append(boxes)
    t3 = time.time()
    return all_boxes


def load_class_names(namesfile):
    class_names = []
    with open(namesfile, 'r') as fp:
        lines = fp.readlines()
    for line in lines:
        line = line.rstrip()
        class_names.append(line)
    return class_names


def scale_bboxes(bboxes, width, height):
    import copy
    dets = copy.deepcopy(bboxes)
    for i in range(len(dets)):
        dets[i][0] = dets[i][0] * width
        dets[i][1] = dets[i][1] * height
        dets[i][2] = dets[i][2] * width
        dets[i][3] = dets[i][3] * height
    return dets


def file_lines(thefilepath):
    count = 0
    thefile = open(thefilepath, 'rb')
    while True:
        buffer = thefile.read(8192*1024)
        if not buffer:
            break
        count += buffer.count(b'\n')
    thefile.close()
    return count


def get_image_size(fname):
    '''Determine the image type of fhandle and return its size.
    from draco'''
    with open(fname, 'rb') as fhandle:
        head = fhandle.read(24)
        if len(head) != 24:
            return
        if imghdr.what(fname) == 'png':
            check = struct.unpack('>i', head[4:8])[0]
            if check != 0x0d0a1a0a:
                return
            width, height = struct.unpack('>ii', head[16:24])
        elif imghdr.what(fname) == 'gif':
            width, height = struct.unpack('<HH', head[6:10])
        elif imghdr.what(fname) == 'jpeg' or imghdr.what(fname) == 'jpg':
            try:
                fhandle.seek(0)  # Read 0xff next
                size = 2
                ftype = 0
                while not 0xc0 <= ftype <= 0xcf:
                    fhandle.seek(size, 1)
                    byte = fhandle.read(1)
                    while ord(byte) == 0xff:
                        byte = fhandle.read(1)
                    ftype = ord(byte)
                    size = struct.unpack('>H', fhandle.read(2))[0] - 2
                # We are at a SOFn block
                fhandle.seek(1, 1)  # Skip `precision' byte.
                height, width = struct.unpack('>HH', fhandle.read(4))
            except Exception:  # IGNORE:W0703
                return
        else:
            return
        return width, height


def logging(message):
    print(('%s %s' % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), message)))


def set_default_context_by_args(args):
    ngpus = len(args.gpus.split(','))
    assert ngpus == 1, 'muti-gpu training is not supported so far. Given {} (size={})'.format(
        args.gpus, ngpus)

    from nnabla.ext_utils import get_extension_context
    ext = 'cpu'
    if args.use_cuda:
        ext = 'cudnn'
    ctx = get_extension_context(ext, device_id=args.gpus)
    nnabla.set_default_context(ctx)
