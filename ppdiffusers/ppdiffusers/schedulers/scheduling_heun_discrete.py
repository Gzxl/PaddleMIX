# Copyright (c) 2023 PaddlePaddle Authors. All Rights Reserved.
# Copyright 2022 Katherine Crowson, The HuggingFace Team and hlky. All rights reserved.
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

import math
from typing import List, Optional, Tuple, Union

import numpy as np
import paddle

from ..configuration_utils import ConfigMixin, register_to_config
from .scheduling_utils import (KarrasDiffusionSchedulers, SchedulerMixin,
                               SchedulerOutput)


# Copied from ppdiffusers.schedulers.scheduling_ddpm.betas_for_alpha_bar
def betas_for_alpha_bar(num_diffusion_timesteps,
                        max_beta=0.999) -> paddle.Tensor:
    """
    Create a beta schedule that discretizes the given alpha_t_bar function, which defines the cumulative product of
    (1-beta) over time from t = [0,1].

    Contains a function alpha_bar that takes an argument t and transforms it to the cumulative product of (1-beta) up
    to that part of the diffusion process.


    Args:
        num_diffusion_timesteps (`int`): the number of betas to produce.
        max_beta (`float`): the maximum beta to use; use values lower than 1 to
                     prevent singularities.

    Returns:
        betas (`np.ndarray`): the betas used by the scheduler to step the model outputs
    """

    def alpha_bar(time_step):
        return math.cos((time_step + 0.008) / 1.008 * math.pi / 2)**2

    betas = []
    for i in range(num_diffusion_timesteps):
        t1 = i / num_diffusion_timesteps
        t2 = (i + 1) / num_diffusion_timesteps
        betas.append(min(1 - alpha_bar(t2) / alpha_bar(t1), max_beta))
    return paddle.to_tensor(betas, dtype=paddle.float32)


class HeunDiscreteScheduler(SchedulerMixin, ConfigMixin):
    """
    Implements Algorithm 2 (Heun steps) from Karras et al. (2022). for discrete beta schedules. Based on the original
    k-diffusion implementation by Katherine Crowson:
    https://github.com/crowsonkb/k-diffusion/blob/481677d114f6ea445aa009cf5bd7a9cdee909e47/k_diffusion/sampling.py#L90

    [`~ConfigMixin`] takes care of storing all config attributes that are passed in the scheduler's `__init__`
    function, such as `num_train_timesteps`. They can be accessed via `scheduler.config.num_train_timesteps`.
    [`SchedulerMixin`] provides general loading and saving functionality via the [`SchedulerMixin.save_pretrained`] and
    [`~SchedulerMixin.from_pretrained`] functions.

    Args:
        num_train_timesteps (`int`): number of diffusion steps used to train the model. beta_start (`float`): the
        starting `beta` value of inference. beta_end (`float`): the final `beta` value. beta_schedule (`str`):
            the beta schedule, a mapping from a beta range to a sequence of betas for stepping the model. Choose from
            `linear` or `scaled_linear`.
        trained_betas (`np.ndarray`, optional):
            option to pass an array of betas directly to the constructor to bypass `beta_start`, `beta_end` etc.
            options to clip the variance used when adding noise to the denoised sample. Choose from `fixed_small`,
            `fixed_small_log`, `fixed_large`, `fixed_large_log`, `learned` or `learned_range`.
        prediction_type (`str`, default `epsilon`, optional):
            prediction type of the scheduler function, one of `epsilon` (predicting the noise of the diffusion
            process), `sample` (directly predicting the noisy sample`) or `v_prediction` (see section 2.4
            https://imagen.research.google/video/paper.pdf)
        use_karras_sigmas (`bool`, *optional*, defaults to `False`):
             This parameter controls whether to use Karras sigmas (Karras et al. (2022) scheme) for step sizes in the
             noise schedule during the sampling process. If True, the sigmas will be determined according to a sequence
             of noise levels {σi} as defined in Equation (5) of the paper https://arxiv.org/pdf/2206.00364.pdf.
    """

    _compatibles = [e.name for e in KarrasDiffusionSchedulers]
    order = 2

    @register_to_config
    def __init__(
            self,
            num_train_timesteps: int=1000,
            beta_start: float=0.00085,  # sensible defaults
            beta_end: float=0.012,
            beta_schedule: str="linear",
            trained_betas: Optional[Union[np.ndarray, List[float]]]=None,
            prediction_type: str="epsilon",
            use_karras_sigmas: Optional[bool]=False, ):
        if trained_betas is not None:
            self.betas = paddle.to_tensor(trained_betas, dtype=paddle.float32)
        elif beta_schedule == "linear":
            self.betas = paddle.linspace(
                beta_start, beta_end, num_train_timesteps, dtype=paddle.float32)
        elif beta_schedule == "scaled_linear":
            # this schedule is very specific to the latent diffusion model.
            self.betas = (paddle.linspace(
                beta_start**0.5,
                beta_end**0.5,
                num_train_timesteps,
                dtype=paddle.float32, )**2)
        elif beta_schedule == "squaredcos_cap_v2":
            # Glide cosine schedule
            self.betas = betas_for_alpha_bar(num_train_timesteps)
        else:
            raise NotImplementedError(
                f"{beta_schedule} does is not implemented for {self.__class__}")

        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = paddle.cumprod(self.alphas, 0)

        #  set all values
        self.set_timesteps(num_train_timesteps, num_train_timesteps)
        self.use_karras_sigmas = use_karras_sigmas

    def index_for_timestep(self, timestep, schedule_timesteps=None):
        if schedule_timesteps is None:
            schedule_timesteps = self.timesteps

        indices = (schedule_timesteps == timestep).nonzero()

        if self.state_in_first_order:
            pos = -1
        else:
            pos = 0
        return indices[pos].item()

    def scale_model_input(
            self,
            sample: paddle.Tensor,
            timestep: Union[float, paddle.Tensor], ) -> paddle.Tensor:
        """
        Args:
        Ensures interchangeability with schedulers that need to scale the denoising model input depending on the
        current timestep.
            sample (`paddle.Tensor`): input sample timestep (`int`, optional): current timestep
        Returns:
            `paddle.Tensor`: scaled input sample
        """
        step_index = self.index_for_timestep(timestep)

        sigma = self.sigmas[step_index]
        sample = sample / ((sigma**2 + 1)**0.5)
        return sample

    def set_timesteps(
            self,
            num_inference_steps: int,
            num_train_timesteps: Optional[int]=None, ):
        """
        Sets the timesteps used for the diffusion chain. Supporting function to be run before inference.

        Args:
            num_inference_steps (`int`):
                the number of diffusion steps used when generating samples with a pre-trained model.
        """
        self.num_inference_steps = num_inference_steps

        num_train_timesteps = num_train_timesteps or self.config.num_train_timesteps

        timesteps = np.linspace(
            0, num_train_timesteps - 1, num_inference_steps,
            dtype=float)[::-1].copy()

        sigmas = np.array(((1 - self.alphas_cumprod) / self.alphas_cumprod)**
                          0.5)
        log_sigmas = np.log(sigmas)
        sigmas = np.interp(timesteps, np.arange(0, len(sigmas)), sigmas)

        if self.use_karras_sigmas:
            sigmas = self._convert_to_karras(
                in_sigmas=sigmas, num_inference_steps=self.num_inference_steps)
            timesteps = np.array(
                [self._sigma_to_t(sigma, log_sigmas) for sigma in sigmas])

        sigmas = np.concatenate([sigmas, [0.0]]).astype(np.float32)
        sigmas = paddle.to_tensor(sigmas)
        self.sigmas = paddle.concat(
            [sigmas[:1], sigmas[1:-1].repeat_interleave(2), sigmas[-1:]])

        # standard deviation of the initial noise distribution
        self.init_noise_sigma = self.sigmas.max()

        timesteps = paddle.to_tensor(timesteps)
        timesteps = paddle.concat(
            [timesteps[:1], timesteps[1:].repeat_interleave(2)])

        self.timesteps = timesteps.cast(paddle.float32)

        # empty dt and derivative
        self.prev_derivative = None
        self.dt = None

    def _sigma_to_t(self, sigma, log_sigmas):
        # get log sigma
        log_sigma = np.log(sigma)

        # get distribution
        dists = log_sigma - log_sigmas[:, np.newaxis]

        # get sigmas range
        low_idx = (np.cumsum(
            (dists >= 0), axis=0).argmax(axis=0)
                   .clip(max=log_sigmas.shape[0] - 2))
        high_idx = low_idx + 1

        low = log_sigmas[low_idx]
        high = log_sigmas[high_idx]

        # interpolate sigmas
        w = (low - log_sigma) / (low - high)
        w = np.clip(w, 0, 1)

        # transform interpolation to time range
        t = (1 - w) * low_idx + w * high_idx
        t = t.reshape(sigma.shape)
        return t

    def _convert_to_karras(self, in_sigmas: paddle.Tensor,
                           num_inference_steps) -> paddle.Tensor:
        """Constructs the noise schedule of Karras et al. (2022)."""

        sigma_min = in_sigmas[-1].item()
        sigma_max = in_sigmas[0].item()

        rho = 7.0  # 7.0 is the value used in the paper
        ramp = np.linspace(0, 1, num_inference_steps)
        min_inv_rho = sigma_min**(1 / rho)
        max_inv_rho = sigma_max**(1 / rho)
        sigmas = (max_inv_rho + ramp * (min_inv_rho - max_inv_rho))**rho
        return sigmas

    @property
    def state_in_first_order(self):
        return self.dt is None

    def step(
            self,
            model_output: Union[paddle.Tensor, np.ndarray],
            timestep: Union[float, paddle.Tensor],
            sample: Union[paddle.Tensor, np.ndarray],
            return_dict: bool=True, ) -> Union[SchedulerOutput, Tuple]:
        """
        Args:
        Predict the sample at the previous timestep by reversing the SDE. Core function to propagate the diffusion
        process from the learned model outputs (most often the predicted noise).
            model_output (`paddle.Tensor` or `np.ndarray`): direct output from learned diffusion model. timestep
            (`int`): current discrete timestep in the diffusion chain. sample (`paddle.Tensor` or `np.ndarray`):
                current instance of sample being created by diffusion process.
            return_dict (`bool`): option for returning tuple rather than SchedulerOutput class
        Returns:
            [`~schedulers.scheduling_utils.SchedulerOutput`] or `tuple`:
            [`~schedulers.scheduling_utils.SchedulerOutput`] if `return_dict` is True, otherwise a `tuple`. When
            returning a tuple, the first element is the sample tensor.
        """
        step_index = self.index_for_timestep(timestep)

        if self.state_in_first_order:
            sigma = self.sigmas[step_index]
            sigma_next = self.sigmas[step_index + 1]
        else:
            # 2nd order / Heun's method
            sigma = self.sigmas[step_index - 1]
            sigma_next = self.sigmas[step_index]

        # currently only gamma=0 is supported. This usually works best anyways.
        # We can support gamma in the future but then need to scale the timestep before
        # passing it to the model which requires a change in API
        gamma = 0
        sigma_hat = sigma * (gamma + 1)  # Note: sigma_hat == sigma for now

        # 1. compute predicted original sample (x_0) from sigma-scaled predicted noise
        if self.config.prediction_type == "epsilon":
            sigma_input = sigma_hat if self.state_in_first_order else sigma_next
            pred_original_sample = sample - sigma_input * model_output
        elif self.config.prediction_type == "v_prediction":
            sigma_input = sigma_hat if self.state_in_first_order else sigma_next
            pred_original_sample = model_output * (-sigma_input / (
                sigma_input**2 + 1)**0.5) + (sample / (sigma_input**2 + 1))
        elif self.config.prediction_type == "sample":
            raise NotImplementedError(
                "prediction_type not implemented yet: sample")
        else:
            raise ValueError(
                f"prediction_type given as {self.config.prediction_type} must be one of `epsilon`, or `v_prediction`"
            )

        if self.state_in_first_order:
            # 2. Convert to an ODE derivative for 1st order
            derivative = (sample - pred_original_sample) / sigma_hat
            # 3. delta timestep
            dt = sigma_next - sigma_hat

            # store for 2nd order step
            self.prev_derivative = derivative
            self.dt = dt
            self.sample = sample
        else:
            # 2. 2nd order / Heun's method
            derivative = (sample - pred_original_sample) / sigma_next
            derivative = (self.prev_derivative + derivative) / 2

            # 3. take prev timestep & sample
            dt = self.dt
            sample = self.sample

            # free dt and derivative
            # Note, this puts the scheduler in "first order mode"
            self.prev_derivative = None
            self.dt = None
            self.sample = None

        prev_sample = sample + derivative * dt

        if not return_dict:
            return (prev_sample, )

        return SchedulerOutput(prev_sample=prev_sample)

    def add_noise(
            self,
            original_samples: paddle.Tensor,
            noise: paddle.Tensor,
            timesteps: paddle.Tensor, ) -> paddle.Tensor:
        # Make sure sigmas and timesteps have the same dtype as original_samples
        sigmas = self.sigmas.cast(original_samples.dtype)

        schedule_timesteps = self.timesteps
        step_indices = [
            self.index_for_timestep(t, schedule_timesteps) for t in timesteps
        ]

        sigma = sigmas[step_indices].flatten()
        while len(sigma.shape) < len(original_samples.shape):
            sigma = sigma.unsqueeze(-1)

        noisy_samples = original_samples + noise * sigma
        return noisy_samples

    def __len__(self):
        return self.config.num_train_timesteps
