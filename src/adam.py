"""
adam.py
-------
A minimal, dependency-free implementation of the Adam optimizer.

This module has ZERO quantum-specific or project-specific code -- it is a
generic first-order stochastic optimizer that could be dropped into any
numerical optimization problem. It only knows about gradients and parameter
vectors, matching the math derived in 00_overview.ipynb SS3.3.
"""

import numpy as np


class AdamOptimizer:
    """Vector-valued Adam (Kingma & Ba, 2014).

    Parameters
    ----------
    n_params : int
        Number of parameters being optimized.
    lr : float
        Learning rate (eta).
    beta1, beta2 : float
        Exponential decay rates for the first and second moment estimates.
    eps : float
        Small constant for numerical stability.
    """

    def __init__(self, n_params, lr=0.15, beta1=0.9, beta2=0.999, eps=1e-8):
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.m = np.zeros(n_params)
        self.v = np.zeros(n_params)
        self.t = 0

    def step(self, theta, grad):
        """Apply one Adam update and return the new parameter vector."""
        self.t += 1
        self.m = self.beta1 * self.m + (1 - self.beta1) * grad
        self.v = self.beta2 * self.v + (1 - self.beta2) * grad ** 2
        m_hat = self.m / (1 - self.beta1 ** self.t)
        v_hat = self.v / (1 - self.beta2 ** self.t)
        return theta - self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
