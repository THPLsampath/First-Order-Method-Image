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

import nnabla as nn
from nnabla import logger
import nnabla.functions as F

import model
from _mnist_data import load_mnist

import os
import numpy as np


def get_args(monitor_path='tmp.monitor.capsnet'):
    """
    Get command line arguments.
    """
    import argparse
    import os
    description = "Capsule Net."
    parser = argparse.ArgumentParser(description)
    parser.add_argument("--monitor-path", "-m",
                        type=str, default=monitor_path,
                        help='Path monitoring logs saved.')
    parser.add_argument('--context', '-c', type=str,
                        default=None, help="Extension modules. ex) 'cpu', 'cudnn'.")
    parser.add_argument("--device-id", "-d", type=str, default='0',
                        help='Device ID the training run on. This is only valid if you specify `-c cudnn`.')
    parser.add_argument("--type-config", "-t", type=str, default='float',
                        help='Type of computation. e.g. "float", "half".')
    args = parser.parse_args()
    assert os.path.isdir(
        args.monitor_path), "Run train.py before running this."
    return args


def model_tweak_digitscaps(batch_size):
    '''
    '''
    image = nn.Variable((batch_size, 1, 28, 28))
    label = nn.Variable((batch_size, 1))
    x = image / 255.0
    t_onehot = F.one_hot(label, (10,))
    with nn.parameter_scope("capsnet"):
        _, _, _, caps, _ = model.capsule_net(
            x, test=True, aug=False, grad_dynamic_routing=True)
    noise = nn.Variable((batch_size, 1, caps.shape[2]))
    with nn.parameter_scope("capsnet_reconst"):
        recon = model.capsule_reconstruction(caps, t_onehot, noise)
    return image, label, noise, recon


def draw_images(adigits, padsize=1, padval=128):
    '''
    Args:
        adigits (numpy.ndarray): [16, 11, 1, 28, 28]. assume uint8

    '''
    d = np.squeeze(adigits, axis=2)
    fh, fw, h, w = d.shape
    hp = h + padsize
    wp = w + padsize
    padding = (
        (0, 0),
        (0, 0),
        (0, padsize),
        (0, padsize))
    d = np.pad(d, padding, mode='constant', constant_values=(padval, padval))
    d = d.transpose(0, 2, 1, 3).reshape((fh * hp, fw * wp))
    return d


def load_parameters(monitor_path):
    '''
    '''
    import glob
    param_files = sorted(glob.glob(os.path.join(monitor_path, 'params_*.h5')))

    # use latest
    logger.info('Loading `%s`.' % param_files[-1])
    _ = nn.load_parameters(param_files[-1])


def main():
    '''
    '''
    args = get_args()

    # Get context.
    from nnabla.ext_utils import get_extension_context
    logger.info("Running in %s" % args.context)
    ctx = get_extension_context(
        args.context, device_id=args.device_id, type_config=args.type_config)
    nn.set_default_context(ctx)

    # Load parameters
    load_parameters(args.monitor_path)

    # Build model
    image, label, noise, recon = model_tweak_digitscaps(10)

    # Get images from 0 to 10.
    images, labels = load_mnist(train=False)
    batch_images = []
    batch_labels = []
    ind = 123
    for i in range(10):
        class_images = images[labels.flat == i]
        img = class_images[min(class_images.shape[0], ind)]
        batch_images.append(img)
        batch_labels.append(i)
    batch_images = np.stack(batch_images, axis=0)
    batch_labels = np.array(batch_labels).reshape(-1, 1)

    # Generate reconstructed images with tweaking capsules
    image.d = batch_images
    label.d = batch_labels
    results = []
    for d in range(noise.shape[2]):  # 16
        for r in np.arange(-0.25, 0.30, 0.05):
            batch_noise = np.zeros(noise.shape)
            batch_noise[..., d] += r
            noise.d = batch_noise
            recon.forward(clear_buffer=True)
            results.append(recon.d.copy())
    # results shape: [16, 11, 10, 1, 28, 28]
    results = np.array(results).reshape((noise.shape[2], -1) + image.shape)

    # Draw tweaked images
    from nnabla.utils.image_utils import imsave
    for i in range(10):
        adigit = (results[:, :, i] * 255).astype(np.uint8)
        drawn = draw_images(adigit)
        imsave(os.path.join(args.monitor_path, 'tweak_digit_%d.png' % i), drawn)


if __name__ == '__main__':
    main()
