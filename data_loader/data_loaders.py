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

        en_dep_file = './data/raw/signal.al.elaser.IP03.edeplist.mat'
        self.en_dep3 = EcalDataIO.ecalmatio(en_dep_file)
        en_dep_file = './data/raw/signal.al.elaser.IP05.edeplist.mat'
        self.en_dep5 = EcalDataIO.ecalmatio(en_dep_file)
        en_file = './data/raw/signal.al.elaser.IP03.energy.mat'
        self.energies3 = EcalDataIO.energymatio(en_file)
        en_file = './data/raw/signal.al.elaser.IP05.energy.mat'
        self.energies5 = EcalDataIO.energymatio(en_file)

        # my_keys = self.energies.keys()
        # del_list = list()
        # for key in my_keys:
        #     if len(self.energies[key]) > 200:
        #         del_list.append(key)
        # for key in del_list:
        #     del self.en_dep[key]
        #     del self.energies[key]

        if noise_file is not None:
            self.en_dep_noise = loadmat(noise_file)
        # self.energies = EcalDataIO.xymatio(en_file)

        self.moment = moment
        self.file = file

        # Eliminate multiple numbers of some kind
        # if min_shower_num > 0:
        #     del_list = []
        #     for key in self.energies:
        #         if len(self.energies[key]) < min_shower_num or len(self.energies[key]) >= max_shower_num:
        #             del_list.append(key)
        #     for d in del_list:
        #         del self.energies[d]
        #         del self.en_dep[d]

    def __len__(self):
        return min(len(self.en_dep3), len(self.en_dep5))

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


    def __getitem__(self, idx):

        hf = h5py.File(os.path.join('./', 'num_classes.h5'), 'r')
        num_classes = hf.get('dataset_1')
        num_classes = int(np.array(num_classes))
        hf.close()
        bin_num = num_classes

        if torch.is_tensor(idx):
            idx = idx.tolist()
        key3 = list(self.en_dep3.keys())[idx]
        key5 = list(self.en_dep5.keys())[idx]

        d_tens = torch.zeros((110, 11, 21))  # Formatted as [x_idx, y_idx, z_idx]
        tmp3 = self.en_dep3[key3]
        tmp5 = self.en_dep5[key5]

        # frac = int(np.random.randint(num_classes))
        # frac = 1
        frac = int(np.random.randint(3))


        if frac == 1:
            for z, x, y in tmp5:
                d_tens[x, y, z] += tmp5[(z, x, y)]
        elif frac == 0:
            for z, x, y in tmp3:
                d_tens[x, y, z] += tmp3[(z, x, y)]
        elif frac == 2:
            for z, x, y in tmp3:
                d_tens[x, y, z] += tmp3[(z, x, y)]
            for z, x, y in tmp5:
                d_tens[x, y, z] += tmp5[(z, x, y)]
        # for z, x, y in tmp3:
        #     d_tens[x, y, z] += (frac/num_classes) * tmp3[(z, x, y)]
        # for z, x, y in tmp5:
        #     d_tens[x, y, z] += (1 - frac/num_classes) * tmp5[(z, x, y)]
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

        # d_tens += en_dep_noise <------------- uncomment for noise

        # plt.figure(num=0, figsize=(12, 6))
        # plt.clf()
        # plt.imshow(en_dep_noise.sum(axis=2).squeeze(axis=0), interpolation="nearest", origin="upper", aspect="auto")
        # plt.colorbar()
        # plt.savefig('with_noise')

        en_list3 = torch.Tensor(self.energies3[key3])
        en_list5 = torch.Tensor(self.energies5[key5])
        num_showers3 = len(en_list3)
        num_showers5 = len(en_list5)
        num_showers = num_showers3 + num_showers5

        ######### Energy bins Generation ########

        final_list = frac
        final_list = torch.tensor(final_list, dtype=torch.long)  # Wrap it in a tensor - important for training and testing.
        
        #########################################

        # final_list = torch.tensor([len(en_list)])

        # print(final_list)

        # return d_tens.sum(axis=2)[:,:,:10], final_list, num_showers, idx
        return d_tens.sum(axis=2)[:,:,:], final_list, num_showers, idx
