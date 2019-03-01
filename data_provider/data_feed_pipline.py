#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 19-3-1 上午10:41
# @Author  : Luo Yao
# @Site    : http://icode.baidu.com/repos/baidu/personal-code/Luoyao
# @File    : data_feed_pipline.py
# @IDE: PyCharm
"""
Data feed pipline
"""
import argparse
import os
import os.path as ops
import random
import multiprocessing

import glob
import glog as log
import tensorflow as tf

from context import tf_io_pipline_tools
from context import global_config

CFG = global_config.cfg


def init_args():
    """

    :return:
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset_dir', type=str, help='The source nsfw data dir path')
    parser.add_argument('--tfrecords_dir', type=str, help='The dir path to save converted tfrecords')

    return parser.parse_args()


class DerainDataProducer(object):
    """
    Convert raw image file into tfrecords
    """
    def __init__(self, dataset_dir):
        """

        :param dataset_dir:
        """
        self._dataset_dir = dataset_dir

        self._rain_image_dir = ops.join(dataset_dir, 'rain_image')
        self._clean_image_dir = ops.join(dataset_dir, 'clean_image')

        self._train_example_index_file_path = ops.join(self._dataset_dir, 'train.txt')
        self._test_example_index_file_path = ops.join(self._dataset_dir, 'test.txt')
        self._val_example_index_file_path = ops.join(self._dataset_dir, 'val.txt')

        if not self._is_source_data_complete():
            raise ValueError('Source image data is not complete, '
                             'please check if one of the image folder is not exist')

        if not self._is_training_example_index_file_complete():
            self._generate_training_example_index_file()

    def generate_tfrecords(self, save_dir, step_size=10000):
        """
        Generate tensorflow records file
        :param save_dir:
        :param step_size: generate a tfrecord every step_size examples
        :return:
        """
        def _read_training_example_index_file(_index_file_path):

            assert ops.exists(_index_file_path)

            _example_rain_path_info = []
            _example_clean_path_info = []

            with open(_index_file_path, 'r') as _file:
                for _line in _file:
                    _example_info = _line.rstrip('\r').rstrip('\n').split(' ')
                    _example_rain_path_info.append(_example_info[0])
                    _example_clean_path_info.append(int(_example_info[1]))

            return _example_rain_path_info, _example_clean_path_info

        def _split_writing_tfrecords_task(_example_paths, _example_labels, _flags='train'):

            _split_example_paths = []
            _split_example_labels = []
            _split_tfrecords_save_paths = []

            for i in range(0, len(_example_paths), step_size):
                _split_example_paths.append(_example_paths[i:i + step_size])
                _split_example_labels.append(_example_labels[i:i + step_size])

                if i + step_size > len(_example_paths):
                    _split_tfrecords_save_paths.append(
                        ops.join(save_dir, '{:s}_{:d}_{:d}.tfrecords'.format(_flags, i, len(_example_paths))))
                else:
                    _split_tfrecords_save_paths.append(
                        ops.join(save_dir, '{:s}_{:d}_{:d}.tfrecords'.format(_flags, i, i + step_size)))

            return _split_example_paths, _split_example_labels, _split_tfrecords_save_paths

        # make save dirs
        os.makedirs(save_dir, exist_ok=True)

        # set process pool
        process_pool = multiprocessing.Pool(processes=CFG.TRAIN.CPU_MULTI_PROCESS_NUMS)

        # generate training example tfrecords
        log.info('Generating training example tfrecords')

        train_rain_images_paths, train_clean_images_paths = _read_training_example_index_file(
            self._train_example_index_file_path)
        train_rain_images_paths_split, train_clean_images_paths_split, train_tfrecords_save_paths = \
            _split_writing_tfrecords_task(train_rain_images_paths, train_clean_images_paths, _flags='train')

        for index, example_paths in enumerate(train_rain_images_paths_split):
            process_pool.apply_async(func=tf_io_pipline_tools.write_example_tfrecords,
                                     args=(example_paths,
                                           train_clean_images_paths_split[index],
                                           train_tfrecords_save_paths[index],))

        process_pool.close()
        process_pool.join()

        log.info('Generate training example tfrecords complete')

        # set process pool
        process_pool = multiprocessing.Pool(processes=CFG.TRAIN.CPU_MULTI_PROCESS_NUMS)

        # generate val example tfrecords
        log.info('Generating validation example tfrecords')

        val_rain_images_paths, val_clean_images_paths = _read_training_example_index_file(
            self._val_example_index_file_path)
        val_rain_images_paths_split, val_clean_images_paths_split, val_tfrecords_save_paths = \
            _split_writing_tfrecords_task(val_rain_images_paths, val_clean_images_paths, _flags='val')

        for index, example_paths in enumerate(val_rain_images_paths):
            process_pool.apply_async(func=tf_io_pipline_tools.write_example_tfrecords,
                                     args=(example_paths,
                                           val_clean_images_paths[index],
                                           val_tfrecords_save_paths[index],))
        process_pool.close()
        process_pool.join()

        log.info('Generate validation example tfrecords complete')

        # set process pool
        process_pool = multiprocessing.Pool(processes=CFG.TRAIN.CPU_MULTI_PROCESS_NUMS)

        # generate test example tfrecords
        log.info('Generating testing example tfrecords')

        test_rain_images_paths, test_clean_images_paths = _read_training_example_index_file(
            self._test_example_index_file_path)
        test_rain_images_paths_split, test_clean_images_paths_split, test_tfrecords_save_paths = \
            _split_writing_tfrecords_task(test_rain_images_paths, test_clean_images_paths, _flags='test')

        for index, example_paths in enumerate(test_rain_images_paths):
            process_pool.apply_async(func=tf_io_pipline_tools.write_example_tfrecords,
                                     args=(example_paths,
                                           test_clean_images_paths[index],
                                           test_tfrecords_save_paths[index],))
        process_pool.close()
        process_pool.join()

        log.info('Generate testing example tfrecords complete')

        return

    def _is_source_data_complete(self):
        """
        Check if source data complete
        :return:
        """
        return ops.exists(self._rain_image_dir) and ops.exists(self._clean_image_dir)

    def _is_training_example_index_file_complete(self):
        """
        Check if the training example index file is complete
        :return:
        """
        return \
            ops.exists(self._train_example_index_file_path) and \
            ops.exists(self._test_example_index_file_path) and \
            ops.exists(self._val_example_index_file_path)

    def _generate_training_example_index_file(self):
        """
        Generate training example index file, split source file into 0.75, 0.15, 0.1 for training,
        testing and validation. Each image folder are processed separately
        :return:
        """
        def _gather_example_info():
            """

            :return:
            """
            _info = []
            for _rain_image_path in glob.glob('{:s}/*.png'.format(self._rain_image_dir)):
                _clean_image_name = ops.split(_rain_image_path)[1].replace('rain', 'clean')
                _clean_image_path = ops.join(self._clean_image_dir, _clean_image_name)

                assert ops.exists(_clean_image_path), '{:s} not exist'.format(_clean_image_path)

                _info.append('{:s} {:s}'.format(_rain_image_path, _clean_image_path))

            return _info

        def _split_training_examples(_example_info):

            random.shuffle(_example_info)

            _example_nums = len(_example_info)

            _train_example_info = _example_info[:int(_example_nums * 0.85)]
            _val_example_info = _example_info[int(_example_nums * 0.85):int(_example_nums * 0.9)]
            _test_example_info = _example_info[int(_example_nums * 0.9):]

            return _train_example_info, _test_example_info, _val_example_info

        train_example_info, test_example_info, val_example_info = _split_training_examples(_gather_example_info())

        random.shuffle(train_example_info)
        random.shuffle(test_example_info)
        random.shuffle(val_example_info)

        with open(ops.join(self._dataset_dir, 'train.txt'), 'w') as file:
            file.write(''.join(train_example_info))

        with open(ops.join(self._dataset_dir, 'test.txt'), 'w') as file:
            file.write(''.join(test_example_info))

        with open(ops.join(self._dataset_dir, 'val.txt'), 'w') as file:
            file.write(''.join(val_example_info))

        log.info('Generate training example index file complete')

        return


# class DerainDataFeeder(object):
#     """
#     Read training examples from tfrecords for nsfw model
#     """
#     def __init__(self, dataset_dir, flags='train'):
#         """
#
#         :param dataset_dir:
#         :param flags:
#         """
#         self._dataset_dir = dataset_dir
#
#         self._tfrecords_dir = ops.join(dataset_dir, 'tfrecords')
#         if not ops.exists(self._tfrecords_dir):
#             raise ValueError('{:s} not exist, please check again'.format(self._tfrecords_dir))
#
#         self._dataset_flags = flags.lower()
#         if self._dataset_flags not in ['train', 'test', 'val']:
#             raise ValueError('flags of the data feeder should be \'train\', \'test\', \'val\'')
#
#     def inputs(self, batch_size, num_epochs):
#         """
#         dataset feed pipline input
#         :param batch_size:
#         :param num_epochs:
#         :return: A tuple (images, labels), where:
#                     * images is a float tensor with shape [batch_size, H, W, C]
#                       in the range [-0.5, 0.5].
#                     * labels is an int32 tensor with shape [batch_size] with the true label,
#                       a number in the range [0, CLASS_NUMS).
#         """
#         if not num_epochs:
#             num_epochs = None
#
#         tfrecords_file_paths = glob.glob('{:s}/{:s}*.tfrecords'.format(self._tfrecords_dir, self._dataset_flags))
#         random.shuffle(tfrecords_file_paths)
#
#         with tf.name_scope('input_tensor'):
#
#             # TFRecordDataset opens a binary file and reads one record at a time.
#             # `tfrecords_file_paths` could also be a list of filenames, which will be read in order.
#             dataset = tf.data.TFRecordDataset(tfrecords_file_paths)
#
#             # The map transformation takes a function and applies it to every element
#             # of the dataset.
#             dataset = dataset.map(map_func=tf_io_pipline_tools.decode,
#                                   num_parallel_calls=CFG.TRAIN.CPU_MULTI_PROCESS_NUMS)
#             if self._dataset_flags == 'train':
#                 dataset = dataset.map(map_func=tf_io_pipline_tools.augment_for_train,
#                                       num_parallel_calls=CFG.TRAIN.CPU_MULTI_PROCESS_NUMS)
#             else:
#                 dataset = dataset.map(map_func=tf_io_pipline_tools.augment_for_validation,
#                                       num_parallel_calls=CFG.TRAIN.CPU_MULTI_PROCESS_NUMS)
#             dataset = dataset.map(map_func=tf_io_pipline_tools.normalize,
#                                   num_parallel_calls=CFG.TRAIN.CPU_MULTI_PROCESS_NUMS)
#
#             # The shuffle transformation uses a finite-sized buffer to shuffle elements
#             # in memory. The parameter is the number of elements in the buffer. For
#             # completely uniform shuffling, set the parameter to be the same as the
#             # number of elements in the dataset.
#             if self._dataset_flags != 'test':
#                 dataset = dataset.shuffle(buffer_size=5000)
#                 # repeat num epochs
#                 dataset = dataset.repeat()
#
#             dataset = dataset.batch(batch_size)
#
#             iterator = dataset.make_one_shot_iterator()
#
#         return iterator.get_next(name='{:s}_IteratorGetNext'.format(self._dataset_flags))


if __name__ == '__main__':

    # init args
    args = init_args()

    assert ops.exists(args.dataset_dir), '{:s} not exist'.format(args.dataset_dir)

    producer = DerainDataProducer(dataset_dir=args.dataset_dir)
    producer.generate_tfrecords(save_dir=args.tfrecords_dir, step_size=5000)
