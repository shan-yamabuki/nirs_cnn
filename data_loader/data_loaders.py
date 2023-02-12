import random
from collections import Counter
from pathlib import Path
from scipy.io import loadmat  
import numpy as np
import torch
from torch.utils.data import Dataset
import matplotlib.pyplot as plt
from base import BaseDataLoader
from data_loader import EcalDataIO
import json
import pandas as pd
import pickle

import os
import h5py


# ------------------------------------------------- DATALOADERS ----------------------------------------------------- #


class data_loader(BaseDataLoader):
    """
    Generates a DL from the existing files - train.pt, test.pt generated by the functions in myutils.py
    """

    def __init__(self, data_dir, batch_size, shuffle=True, validation_split=0.0, num_workers=1, training=True):

        if training == True:
            self.dataset = torch.load(Path(data_dir) / "train//train.pt")
        else:
            self.dataset = torch.load(Path(data_dir) / "test//test.pt")

        print("Dataset len: ", len(self.dataset))
        super().__init__(self.dataset, batch_size, shuffle, validation_split, num_workers)


class rand_loader(BaseDataLoader):
    """
    Generates a random dataset object and wrap it with a DL
    """

    def __init__(self, data_dir='', batch_size=128, shuffle=True, validation_split=0.0, num_workers=1, training=True):
        self.dataset = Random_DS(len(self.dataset))

        print("Dataset len: ", len(self.dataset))
        super().__init__(self.dataset, batch_size, shuffle, validation_split, num_workers)


# ___________________________________________________DATASETS__________________________________________________________#


class Bin_energy_data(Dataset):
    """
    General dataset object -
    __getitem__: returns the d_tens (calorimeter matrix data), and the relevant info for the network to learn.
                 Either the num_showers for N training, or the mean energy for E training or final_list for 20bin train.
                 Also returns the num_showers and idx parameter for test purposes.
    """

    def __init__(self, en_dep_file, en_file, moment=1, min_shower_num=0, max_shower_num=10000, file=0, noise_file=None):

        self.en_dep = EcalDataIO.ecalmatio(en_dep_file)  # Dict with 100000 samples {(Z,X,Y):energy_stamp}
        self.energies = EcalDataIO.energymatio(en_file)
        if noise_file is not None:
            self.en_dep_noise = loadmat(noise_file)
        # self.energies = EcalDataIO.xymatio(en_file)

        self.moment = moment
        self.file = file

        # Eliminate multiple numbers of some kind
        if min_shower_num > 0:
            del_list = []
            for key in self.energies:
                if len(self.energies[key]) < min_shower_num or len(self.energies[key]) >= max_shower_num:
                    del_list.append(key)
            for d in del_list:
                del self.energies[d]
                del self.en_dep[d]

    def __len__(self):
        return len(self.en_dep)

    def calculate_moment(self, moment_num, en_list, normalize=True):
        """
        Returns a list of moment_num length, containing all the moments for the given energy list.
        More here: https://towardsdatascience.com/moment-generating-function-explained-27821a739035
        """
        res = []
        if not torch.is_tensor(en_list):
            en_list = torch.Tensor(en_list)

        first = torch.mean(en_list)
        res.append(torch.mean(en_list))
        if moment_num == 1:
            return res

        l = []
        for val in en_list:
            # l.append((val - first) ** 2)
            l.append(val ** 2)
        second = torch.mean(torch.Tensor(l))
        res.append(second)

        if moment_num == 2:
            return res

        for i in range(3, moment_num + 1):
            l = []
            for val in en_list:
                if normalize:
                    # t = (val - first) ** i
                    t = (val) ** i
                    s = second ** i
                    r = t / s
                    l.append(r)
                else:
                    # t = (val - first) ** i
                    t = val ** i
                    l.append(t)

            tmp = torch.mean(torch.Tensor(l))
            res.append(tmp)

        return res

    def random_sample_for_addition(self, data, n, num_samples):

        """
        This function takes the sample and adds to it another n samples. The matrices are superpositioned and the
        number of showers N is summed.
        """

        samples = random.sample(list(self.en_dep.keys()), num_samples)

        # A loop allowing only certain num of showers to be added.
        # while True:
        #     if len(self.energies[samples[0]]) != 1:
        #         samples = random.sample(list(self.en_dep.keys()), num_samples)
        #     else:
        #         break

        sample = torch.zeros((110, 11, 21))  # Formatted as [x_idx, y_idx, z_idx]
        N = 0
        for key in samples:
            N += len(self.energies[key])
            tmp = self.en_dep[key]
            # sum the samples:
            for z, x, y in tmp:
                sample[x, y, z] = sample[x, y, z] + tmp[(z, x, y)]

        print(f"Orig - {n}, Add - {N}")
        data = data + sample
        n = n + N
        print(f"sum - {n}")
        return data, n

    def __getitem__(self, idx):

        if torch.is_tensor(idx):
            idx = idx.tolist()
        key = list(self.en_dep.keys())[idx]

        d_tens = torch.zeros((110, 11, 21))  # Formatted as [x_idx, y_idx, z_idx]
        tmp = self.en_dep[key]

        for z, x, y in tmp:
            d_tens[x, y, z] = tmp[(z, x, y)]
        d_tens = d_tens.unsqueeze(0)  # Only in conv3d

        key_noise = str(np.random.random_integers(999))

        en_dep_noise = torch.zeros((110, 11, 21))
        for i in range(en_dep_noise.shape[0]):
            for j in range(en_dep_noise.shape[1]):
                for k in range(en_dep_noise.shape[2]):
                    en_dep_noise[i,j,k] = self.en_dep_noise[key_noise][k,i,j]
        # plt.figure(num=0, figsize=(12, 6))
        # plt.clf()
        # plt.imshow(d_tens.sum(axis=2).squeeze(axis=0), interpolation="nearest", origin="upper", aspect="auto")
        # plt.colorbar()
        # plt.savefig('without_noise')
        with open('without_noise.npy', 'wb') as f:
            np.save(f, d_tens)

        d_tens += en_dep_noise

        with open('with_noise.npy', 'wb') as f:
            np.save(f, d_tens)

        # plt.figure(num=0, figsize=(12, 6))
        # plt.clf()
        # plt.imshow(en_dep_noise.sum(axis=2).squeeze(axis=0), interpolation="nearest", origin="upper", aspect="auto")
        # plt.colorbar()
        # plt.savefig('with_noise')

        en_list = torch.Tensor(self.energies[key])
        num_showers = len(en_list)

        #########################################
        ############ Shrink sample ##############
        # d_tens = d_tens[:, 4:7, 0:10]
        # d_tens = torch.transpose(d_tens, 0, 1)
        #########################################

        #########################################
        ############ Layer Removal ##############
        # Zerofi Z layers
        # for i in range(0, 7):
        #     d_tens[:, :, (20 - i)] = 0

        # Zerofi Y layers
        # for i in range(0, 6):
        #     d_tens[:, (10 - i), :] = 0
        #     d_tens[:, i, :] = 0
        #########################################

        #########################################
        ########## Alpha Experiment #############
        # alpha = 1
        #
        # d_tens = np.cos(np.deg2rad(alpha)) * d_tens + np.sin(np.deg2rad(alpha)) * torch.rand(torch.Size([110, 11, 21]))
        # d_tens = np.cos(np.deg2rad(alpha)) * d_tens + np.sin(np.deg2rad(alpha)) * torch.rand(torch.Size([110, 3, 10]))
        # d_tens = (1-alpha) * d_tens + (alpha) * torch.rand(torch.Size([110, 11, 21]))
        #########################################

        #########################################
        ############ Normalization ##############
        # if self.file == 3:
        #     d_tens = (d_tens - 0.0935) / 1.4025
        #########################################

        #########################################
        ############ Superposition ##############
        # d_tens, num_showers = self.random_sample_for_addition(d_tens, num_showers, 1)
        #########################################

        #########################################
        ######### Energy bins Generation ########
        hf = h5py.File(os.path.join('./', 'num_classes.h5'), 'r')
        num_classes = hf.get('dataset_1')
        num_classes = int(np.array(num_classes))
        hf.close()
        bin_num = num_classes

        final_list = [0] * bin_num  # The 20 here is the bin number - it may be changed of course.
        bin_list = np.linspace(1, 13, bin_num)  # Generate the bin limits
        binplace = np.digitize(en_list, bin_list)  # Divide the list into bins
        bin_partition = Counter(binplace)  # Count the number of showers for each bin.
        for k in bin_partition.keys():
            final_list[int(k) - 1] = bin_partition[k]
        n = sum(final_list)
        # final_list = [f / n for f in final_list]    # Bin Normalization by sum
        final_list = torch.Tensor(final_list)  # Wrap it in a tensor - important for training and testing.
        
        #########################################

        # final_list = torch.tensor([len(en_list)])



        # with open('sum_pixels.pickle', 'rb') as file:
        #     sum_pixels = pickle.load(file)
        # sum_pixels[str(idx)] = float(d_tens.sum())
        # with open('sum_pixels.pickle', 'wb') as file:
        #     pickle.dump(sum_pixels, file, protocol=pickle.HIGHEST_PROTOCOL)

        return d_tens.sum(axis=2)[:,:,:], final_list, num_showers, idx
        # return d_tens.sum(axis=2)[:,:,:3], final_list, num_showers, idx
