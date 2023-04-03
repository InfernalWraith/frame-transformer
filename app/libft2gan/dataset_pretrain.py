import os
import random
import numpy as np
import torch
import torch.utils.data
import torch.nn.functional as F
from libft2gan.dataset_utils import apply_channel_drop, apply_dynamic_range_mod, apply_multiplicative_noise, apply_random_eq, apply_stereo_spatialization, apply_time_stretch, apply_random_phase_noise, apply_time_masking, apply_frequency_masking, apply_time_masking2, apply_frequency_masking2, apply_emphasis, apply_deemphasis, apply_pitch_shift, apply_masking, apply_harmonic_distortion
import librosa

class VoxAugDataset(torch.utils.data.Dataset):
    def __init__(self, instrumental_lib=[], pretraining_lib=[], vocal_lib=[], is_validation=False, n_fft=2048, hop_length=1024, cropsize=256, sr=44100, seed=0, data_limit=None):
        self.is_validation = is_validation
        self.vocal_list = []
        self.curr_list = []
        self.epoch = 0

        self.max_bin = n_fft // 2
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.cropsize = cropsize

        for mp in instrumental_lib:
            mixes = [os.path.join(mp, f) for f in os.listdir(mp) if os.path.isfile(os.path.join(mp, f))]

            for m in mixes:
                self.curr_list.append(m)

        for mp in pretraining_lib:
            mixes = [os.path.join(mp, f) for f in os.listdir(mp) if os.path.isfile(os.path.join(mp, f))]

            for m in mixes:
                self.curr_list.append(m)
            
        if not is_validation and len(vocal_lib) != 0:
            for vp in vocal_lib:
                vox = [os.path.join(vp, f) for f in os.listdir(vp) if os.path.isfile(os.path.join(vp, f))]

                for v in vox:
                    self.vocal_list.append(v)

        def key(p):
            return os.path.basename(p)
        
        self.vocal_list.sort(key=key)
        self.curr_list.sort(key=key)
        random.Random(seed).shuffle(self.vocal_list)
        random.Random(seed+1).shuffle(self.curr_list)

    def set_epoch(self, epoch):
        self.epoch = epoch

    def __len__(self):
        return len(self.curr_list)

    def _get_vocals(self, idx):
        path = str(self.vocal_list[(self.epoch + idx) % len(self.vocal_list)])
        vdata = np.load(path, allow_pickle=True)
        V, Vc = vdata['X'], vdata['c']

        if np.random.uniform() < 0.5:
            V = apply_time_stretch(V, self.cropsize)
        elif V.shape[2] > self.cropsize:
            start = np.random.randint(0, V.shape[2] - self.cropsize)
            V = V[:, :, start:start+self.cropsize]

        P = np.angle(V)
        M = np.abs(V)

        augmentations = [
            (0.02, apply_channel_drop, { "channel": np.random.randint(1,3), "alpha": np.random.uniform() }),
            (0.2, apply_pitch_shift, { "pitch_shift": np.random.uniform(-12, 12) }),
        ]

        random.shuffle(augmentations)

        for p, aug, args in augmentations:
            if np.random.uniform() < p:
                M, P = aug(M, P, **args)

        V = M * np.exp(1.j * P)

        if np.random.uniform() < 0.5:
            V = V[::-1]

        return V

    def _augment_mix(self, X, c):
        if X.shape[2] > self.cropsize:
            start = np.random.randint(0, X.shape[2] - self.cropsize)
            X = X[:, :, start:start+self.cropsize]

        P = np.angle(X)
        M = np.abs(X)

        augmentations = [
            (0.25, apply_dynamic_range_mod, { "c": c, "threshold": np.random.uniform(), "gain": np.random.uniform(), }),
            (0.25, apply_multiplicative_noise, { "loc": 1, "scale": np.random.uniform(0, 0.5), }),
            (0.25, apply_random_eq, { "min": np.random.uniform(0, 1), "max": np.random.uniform(1, 2), }),
            (0.25, apply_stereo_spatialization, { "c": c, "alpha": np.random.uniform(0, 1) }),            
            (0.25, apply_masking, { "c": c, "num_masks": np.random.randint(0, 6), "max_mask_percentage": np.random.uniform(0, 0.2), "alpha": np.random.uniform() }),
            (0.25, apply_random_phase_noise, { "strength": np.random.uniform(0, 0.5)}),
            (0.25, apply_emphasis, { "coef": np.random.uniform(0.75, 1) }),
            (0.25, apply_deemphasis, { "coef": np.random.uniform(0.75, 1) }),
        ] if np.random.uniform() > 0.02 else []

        random.shuffle(augmentations)

        for p, aug, args in augmentations:
            if np.random.uniform() < p:
                M, P = aug(M, P, **args)

        X = M * np.exp(1.j * P)

        if np.random.uniform() < 0.5:
            X = X[::-1]

        return X

    def _get_instruments(self, X, c):
        if X.shape[2] > self.cropsize:
            start = np.random.randint(0, X.shape[2] - self.cropsize)
            X = X[:, :, start:start+self.cropsize]

        P = np.angle(X)
        M = np.abs(X)

        augmentations = [
            (0.01, apply_channel_drop, { "channel": np.random.randint(1,3), "alpha": np.random.uniform() })
        ]

        random.shuffle(augmentations)

        for p, aug, args in augmentations:
            if np.random.uniform() < p:
                M, P = aug(M, P, **args)

        X = M * np.exp(1.j * P)

        if np.random.uniform() < 0.5:
            X = X[::-1]

        return X
    
    def _get_wave(self, X, c):
        left_s = np.pad(librosa.istft((np.abs(X[0]) / c) + np.exp(1.j * np.angle(X[0])), hop_length=self.hop_length), ((0, self.hop_length)))
        right_s = np.pad(librosa.istft((np.abs(X[1]) / c) + np.exp(1.j * np.angle(X[1])), hop_length=self.hop_length), ((0, self.hop_length)))
        S = np.expand_dims(np.stack([left_s, right_s], axis=0), axis=2).reshape((2, left_s.shape[0] // X.shape[2], -1))
        return S
    
    def __getitem__(self, idx):
        path = str(self.curr_list[idx % len(self.curr_list)])
        data = np.load(path, allow_pickle=True)
        aug = 'Y' not in data.files

        X, c = data['X'], data['c']
        Y = X if aug else data['Y']
        V = None
        
        if not self.is_validation:
            Y = self._get_instruments(Y, c)
            X = Y

            if path.find('instruments') != -1:
                V = self._get_vocals(idx)
                Y = Y if np.random.uniform() < 0.4 else Y + V
                c = np.max([c, np.abs(X).max()])

            X = Y if np.random.uniform() < 0.08 else self._augment_mix(Y, c)

        X = np.clip(np.abs(X) / c, 0, 1)
        Y = np.clip(np.abs(Y) / c, 0, 1)

        return X.astype(np.float32), Y.astype(np.float32)