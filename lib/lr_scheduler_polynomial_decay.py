from torch.optim import Optimizer
from torch.optim.lr_scheduler import _LRScheduler

class PolynomialDecayScheduler(_LRScheduler):
    def __init__(self, optimizer, base_lr=1e-3, target=1e-8, power=1.0, num_decay_steps=120000, start_step=16000, current_step=0, verbose=True, verbose_skip_steps=1000):
        self.base_lr = base_lr
        self.start_step = start_step
        self.current_step_init = current_step
        self.current_step = current_step
        self.verbose = verbose
        self.verbose_skip_steps = verbose_skip_steps
        self.num_decay_steps = num_decay_steps
        self.target = target
        self.power = power

        if not isinstance(optimizer, Optimizer):
            raise TypeError('{} is not an Optimizer'.format(
                type(optimizer).__name__))

        self.optimizer = optimizer
        
        super().__init__(optimizer)

    def _reset(self):
        self.current_step = self.current_step_init

        if self.current_step > self.start_step and self.current_step < (self.start_step + self.num_decay_steps + 1):
            self.current_lr =  (self.base_lr - self.target) * ((1 - (self.current_step - self.start_step) / self.num_decay_steps) ** (self.power)) + self.target

            for i, param_group in enumerate(self.optimizer.param_groups):
                param_group['lr'] = self.current_lr
                if self.verbose and self.current_step % self.verbose_skip_steps == 0:
                    print(' Step {:5d} of {:5d}: set learning rate'
                            ' of group {} to {:.4e}.'.format(self.current_step, self.start_step + self.num_decay_steps, i, self.current_lr))

        if self.current_step < self.start_step + self.num_decay_steps + 1:
            self.current_step = self.current_step + 1

    def step(self):
        if self.current_step > self.start_step and self.current_step < (self.start_step + self.num_decay_steps + 1):
            self.current_lr =  (self.base_lr - self.target) * ((1 - (self.current_step - self.start_step) / self.num_decay_steps) ** (self.power)) + self.target

            for i, param_group in enumerate(self.optimizer.param_groups):
                param_group['lr'] = self.current_lr
                if self.verbose and self.current_step % self.verbose_skip_steps == 0:
                    print(' Step {:5d} of {:5d}: decreased learning rate'
                            ' of group {} to {:.4e}.'.format(self.current_step, self.start_step + self.num_decay_steps, i, self.current_lr))

        if self.current_step < self.start_step + self.num_decay_steps + 1:
            self.current_step = self.current_step + 1

    def state_dict(self):
        return {key: value for key, value in self.__dict__.items() if key != 'optimizer'}

    def load_state_dict(self, state_dict):
        self.__dict__.update(state_dict)