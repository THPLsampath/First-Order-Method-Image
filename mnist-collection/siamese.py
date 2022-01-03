# Copyright 2017,2018,2019,2020,2021 Sony Corporation.
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

from __future__ import absolute_import
from six.moves import range

from contextlib import contextmanager
import numpy as np
import os

import nnabla as nn
import nnabla.logger as logger
import nnabla.functions as F
import nnabla.parametric_functions as PF
import nnabla.solvers as S

from _checkpoint_nnp_util import save_checkpoint, load_checkpoint, save_nnp
from args import get_args
from mnist_data import data_iterator_mnist
import nnabla.utils.save as save


def mnist_lenet_feature(image, test=False):
    """
    Construct LeNet for MNIST.
    """
    c1 = F.elu(PF.convolution(image, 20, (5, 5), name='conv1'))
    c1 = F.average_pooling(c1, (2, 2))
    c2 = F.elu(PF.convolution(c1, 50, (5, 5), name='conv2'))
    c2 = F.average_pooling(c2, (2, 2))
    c3 = F.elu(PF.affine(c2, 500, name='fc3'))
    c4 = PF.affine(c3, 10, name='fc4')
    c5 = PF.affine(c4, 2, name='fc_embed')
    return c5


def mnist_lenet_siamese(x0, x1, test=False):
    """"""
    h0 = mnist_lenet_feature(x0, test)
    h1 = mnist_lenet_feature(x1, test)  # share weights
    # h = (h0 - h1) ** 2 # equivalent
    h = F.squared_error(h0, h1)
    p = F.sum(h, axis=1)
    return p


def contrastive_loss(sd, l, margin=1.0, eps=1e-4):
    """
    This implements contrastive loss function given squared difference `sd` and labels `l` in {0, 1}.

    f(sd, l) = l * sd + (1 - l) * max(0, margin - sqrt(sd))^2

    NNabla implements various basic arithmetic operations. That helps write custom operations
    with composition like this. This is handy, but still implementing NNabla Function in C++
    gives you better performance advantage.
    """
    sim_cost = l * sd
    dissim_cost = (1 - l) * \
        (F.maximum_scalar(margin - (sd + eps) ** (0.5), 0) ** 2)
    return sim_cost + dissim_cost


class MnistSiameseDataIterator(object):

    def __init__(self, itr0, itr1):
        self.itr0 = itr0
        self.itr1 = itr1

    def next(self):
        x0, l0 = self.itr0.next()
        x1, l1 = self.itr1.next()
        sim = (l0 == l1).astype(np.int).flatten()
        return x0 / 255., x1 / 255., sim


def siamese_data_iterator(batch_size, train, rng=None):
    itr0 = data_iterator_mnist(batch_size, train=train, rng=rng, shuffle=True)
    itr1 = data_iterator_mnist(batch_size, train=train, rng=rng, shuffle=True)
    return MnistSiameseDataIterator(itr0, itr1)


def train(args):
    """
    Main script.
    """

    # Get context.
    from nnabla.ext_utils import get_extension_context
    logger.info("Running in %s" % args.context)
    ctx = get_extension_context(
        args.context, device_id=args.device_id, type_config=args.type_config)
    nn.set_default_context(ctx)

    # Create CNN network for both training and testing.
    margin = 1.0  # Margin for contrastive loss.

    # TRAIN
    # Create input variables.
    image0 = nn.Variable([args.batch_size, 1, 28, 28])
    image1 = nn.Variable([args.batch_size, 1, 28, 28])
    label = nn.Variable([args.batch_size])
    # Create prediction graph.
    pred = mnist_lenet_siamese(image0, image1, test=False)
    # Create loss function.
    loss = F.mean(contrastive_loss(pred, label, margin))

    # TEST
    # Create input variables.
    vimage0 = nn.Variable([args.batch_size, 1, 28, 28])
    vimage1 = nn.Variable([args.batch_size, 1, 28, 28])
    vlabel = nn.Variable([args.batch_size])
    # Create prediction graph.
    vpred = mnist_lenet_siamese(vimage0, vimage1, test=True)
    vloss = F.mean(contrastive_loss(vpred, vlabel, margin))

    # Create Solver.
    solver = S.Adam(args.learning_rate)
    solver.set_parameters(nn.get_parameters())

    start_point = 0
    if args.checkpoint is not None:
        # load weights and solver state info from specified checkpoint file.
        start_point = load_checkpoint(args.checkpoint, solver)

    # Create monitor.
    import nnabla.monitor as M
    monitor = M.Monitor(args.monitor_path)
    monitor_loss = M.MonitorSeries("Training loss", monitor, interval=10)
    monitor_time = M.MonitorTimeElapsed("Training time", monitor, interval=100)
    monitor_vloss = M.MonitorSeries("Test loss", monitor, interval=10)

    # Initialize DataIterator for MNIST.
    rng = np.random.RandomState(313)
    data = siamese_data_iterator(args.batch_size, True, rng)
    vdata = siamese_data_iterator(args.batch_size, False, rng)

    # Training loop.
    for i in range(start_point, args.max_iter):
        if i % args.val_interval == 0:
            # Validation
            ve = 0.0
            for j in range(args.val_iter):
                vimage0.d, vimage1.d, vlabel.d = vdata.next()
                vloss.forward(clear_buffer=True)
                ve += vloss.d
            monitor_vloss.add(i, ve / args.val_iter)
        if i % args.model_save_interval == 0:
            # save checkpoint file
            save_checkpoint(args.model_save_path, i, solver)
        image0.d, image1.d, label.d = data.next()
        solver.zero_grad()
        # Training forward, backward and update
        loss.forward(clear_no_need_grad=True)
        loss.backward(clear_buffer=True)
        solver.weight_decay(args.weight_decay)
        solver.update()
        monitor_loss.add(i, loss.d.copy())
        monitor_time.add(i)

    parameter_file = os.path.join(
        args.model_save_path, 'params_%06d.h5' % args.max_iter)
    nn.save_parameters(parameter_file)


def visualize(args):
    """
    Visualizing embedded digits onto 2D space.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    batch_size = 500

    # Load parameters
    nn.load_parameters(os.path.join(args.model_save_path,
                                    'params_%06d.h5' % args.max_iter))

    # Create embedded network
    image = nn.Variable([batch_size, 1, 28, 28])
    feature = mnist_lenet_feature(image, test=True)

    # Process all images
    features = []
    labels = []
    # Prepare MNIST data iterator

    rng = np.random.RandomState(313)
    data = data_iterator_mnist(batch_size, train=False, rng=rng, shuffle=True)
    for i in range(10000 // batch_size):
        image_data, label_data = data.next()
        image.d = image_data / 255.
        feature.forward(clear_buffer=True)
        features.append(feature.d.copy())
        labels.append(label_data.copy())
    features = np.vstack(features)
    labels = np.vstack(labels)

    # Visualize
    f = plt.figure(figsize=(16, 9))
    for i in range(10):
        c = plt.cm.Set1(i / 10.)
        plt.plot(features[labels.flat == i, 0].flatten(), features[
                 labels.flat == i, 1].flatten(), '.', c=c)
    plt.legend(list(map(str, range(10))))
    plt.grid()
    plt.savefig(os.path.join(args.monitor_path, "embed.png"))


def save_siamese_nnp(args):
    image = nn.Variable([1, 1, 28, 28])
    feature = mnist_lenet_feature(image, test=True)
    contents = save_nnp({'x': image}, {'y': feature}, args.batch_size)
    save.save(os.path.join(args.model_save_path,
                           '{}_result.nnp'.format(args.net)), contents)


if __name__ == '__main__':
    monitor_path = 'tmp.monitor.siamese'
    args = get_args(monitor_path=monitor_path,
                    model_save_path=monitor_path, max_iter=5000)
    train(args)
    visualize(args)
    save_siamese_nnp(args)
