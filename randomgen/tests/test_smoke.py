from functools import partial
import os
import pickle
import sys
import time

import numpy as np
from numpy.testing import (
    assert_,
    assert_almost_equal,
    assert_array_equal,
    assert_equal,
    suppress_warnings,
)
import pytest

from randomgen import (
    DSFMT,
    EFIIX64,
    HC128,
    JSF,
    LXM,
    MT64,
    MT19937,
    PCG32,
    PCG64,
    PCG64DXSM,
    SFMT,
    SPECK128,
    AESCounter,
    ChaCha,
    LCG128Mix,
    Philox,
    Romu,
    ThreeFry,
    Xoroshiro128,
    Xorshift1024,
    Xoshiro256,
    Xoshiro512,
    entropy,
)


@pytest.fixture(
    scope="module",
    params=(
        bool,
        np.int8,
        np.int16,
        np.int32,
        np.int64,
        np.uint8,
        np.uint16,
        np.uint32,
        np.uint64,
    ),
)
def dtype(request):
    return request.param


def params_0(f):
    val = f()
    assert_(np.isscalar(val))
    val = f(10)
    assert_(val.shape == (10,))
    val = f((10, 10))
    assert_(val.shape == (10, 10))
    val = f((10, 10, 10))
    assert_(val.shape == (10, 10, 10))
    val = f(size=(5, 5))
    assert_(val.shape == (5, 5))


def params_1(f, bounded=False):
    a = 5.0
    b = np.arange(2.0, 12.0)
    c = np.arange(2.0, 102.0).reshape(10, 10)
    d = np.arange(2.0, 1002.0).reshape(10, 10, 10)
    e = np.array([2.0, 3.0])
    g = np.arange(2.0, 12.0).reshape(1, 10, 1)
    if bounded:
        a = 0.5
        b = b / (1.5 * b.max())
        c = c / (1.5 * c.max())
        d = d / (1.5 * d.max())
        e = e / (1.5 * e.max())
        g = g / (1.5 * g.max())

    # Scalar
    f(a)
    # Scalar - size
    f(a, size=(10, 10))
    # 1d
    f(b)
    # 2d
    f(c)
    # 3d
    f(d)
    # 1d size
    f(b, size=10)
    # 2d - size - broadcast
    f(e, size=(10, 2))
    # 3d - size
    f(g, size=(10, 10, 1))


def comp_state(state1, state2):
    identical = True
    if isinstance(state1, dict):
        for key in state1:
            identical &= comp_state(state1[key], state2[key])
    elif type(state1) != type(state2):
        identical &= type(state1) == type(state2)
    else:
        if isinstance(state1, (list, tuple, np.ndarray)) and isinstance(
            state2, (list, tuple, np.ndarray)
        ):
            for s1, s2 in zip(state1, state2):
                identical &= comp_state(s1, s2)
        else:
            identical &= state1 == state2
    return identical


def warmup(rg, n=None):
    if n is None:
        n = 11 + np.random.randint(0, 20)
    rg.standard_normal(n)
    rg.standard_normal(n)
    rg.standard_normal(n, dtype=np.float32)
    rg.standard_normal(n, dtype=np.float32)
    rg.integers(0, 2**24, n, dtype=np.uint64)
    rg.integers(0, 2**48, n, dtype=np.uint64)
    rg.standard_gamma(11.0, n)
    rg.standard_gamma(11.0, n, dtype=np.float32)
    rg.random(n, dtype=np.float64)
    rg.random(n, dtype=np.float32)


class RNG(object):
    @classmethod
    def setup_class(cls):
        # Overridden in test classes. Place holder to silence IDE noise
        cls.bit_generator = Xoshiro256
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.max_vector_seed_size = 4

    @classmethod
    def _extra_setup(cls):
        cls.vec_1d = np.arange(2.0, 102.0)
        cls.vec_2d = np.arange(2.0, 102.0)[None, :]
        cls.mat = np.arange(2.0, 102.0, 0.01).reshape((100, 100))
        cls.seed_error = TypeError

    def init_generator(self, seed=None, mode="sequence"):
        if seed is not None:
            return np.random.Generator(self.bit_generator(*seed, mode=mode))
        else:
            return np.random.Generator(self.bit_generator(seed=seed, mode=mode))

    def _reset_state(self):
        self.rg.bit_generator.state = self.initial_state

    def test_init(self):
        rg = self.init_generator()
        state = rg.bit_generator.state
        rg.standard_normal(1)
        rg.standard_normal(1)
        rg.bit_generator.state = state
        new_state = rg.bit_generator.state
        assert_(comp_state(state, new_state))

    def test_advance(self):
        bg = self.rg.bit_generator
        state = bg.state
        if hasattr(self.rg.bit_generator, "advance"):
            kwargs = {}
            if isinstance(bg, (Philox, ThreeFry)):
                kwargs = {"counter": True}
            self.rg.bit_generator.advance(self.advance, **kwargs)
            assert_(not comp_state(state, self.rg.bit_generator.state))
        else:
            bit_gen_name = self.rg.bit_generator.__class__.__name__
            pytest.skip("Advance is not supported by {0}".format(bit_gen_name))

    def test_jump(self):
        state = self.rg.bit_generator.state
        if hasattr(self.rg.bit_generator, "jump") and not isinstance(
            self.rg.bit_generator, PCG64DXSM
        ):
            with pytest.deprecated_call():
                self.rg.bit_generator.jump()
            jumped_state = self.rg.bit_generator.state
            assert_(not comp_state(state, jumped_state))
            self.rg.random(2 * 3 * 5 * 7 * 11 * 13 * 17)
            self.rg.bit_generator.state = state
            with pytest.deprecated_call():
                self.rg.bit_generator.jump()
            rejumped_state = self.rg.bit_generator.state
            assert_(comp_state(jumped_state, rejumped_state))
        else:
            bit_gen_name = self.rg.bit_generator.__class__.__name__
            pytest.skip("jump is not supported by {0}".format(bit_gen_name))

    def test_jumped(self):
        state = self.rg.bit_generator.state
        if hasattr(self.rg.bit_generator, "jumped"):
            new_bit_gen = self.rg.bit_generator.jumped()
            assert isinstance(new_bit_gen, self.rg.bit_generator.__class__)
            assert_(comp_state(state, self.rg.bit_generator.state))
            np.random.Generator(new_bit_gen).random(1000000)
        else:
            bit_gen_name = self.rg.bit_generator.__class__.__name__
            pytest.skip("jumped is not supported by {0}".format(bit_gen_name))

    def test_jumped_against_jump(self):
        if (
            hasattr(self.rg.bit_generator, "jumped")
            and hasattr(self.rg.bit_generator, "jump")
            and not isinstance(self.rg.bit_generator, PCG64DXSM)
        ):
            bg = self.rg.bit_generator
            state = bg.state
            new_bg = bg.jumped()
            with pytest.deprecated_call():
                bg.jump()
            assert_(not comp_state(state, bg.state))
            assert_(not comp_state(state, new_bg.state))
            assert_(comp_state(bg.state, new_bg.state))
        else:
            bit_gen_name = self.rg.bit_generator.__class__.__name__
            pytest.skip("jump or jumped is not supported by {0}".format(bit_gen_name))

    def test_jumped_against_jump_32bit(self):
        if (
            hasattr(self.rg.bit_generator, "jumped")
            and hasattr(self.rg.bit_generator, "jump")
            and not isinstance(self.rg.bit_generator, PCG64DXSM)
        ):
            bg = self.rg.bit_generator
            bg.seed(*self.seed)
            # Draw large prime number of 32bits to move internal state values
            self.rg.random(11587, dtype=np.float32)
            state = bg.state
            new_bg = bg.jumped()
            with pytest.deprecated_call():
                bg.jump()
            assert_(not comp_state(state, bg.state))
            assert_(not comp_state(state, new_bg.state))
            assert_(comp_state(bg.state, new_bg.state))
        else:
            bit_gen_name = self.rg.bit_generator.__class__.__name__
            pytest.skip("jump or jumped is not supported by {0}".format(bit_gen_name))

    def test_uniform(self):
        r = self.rg.uniform(-1.0, 0.0, size=10)
        assert_(len(r) == 10)
        assert_((r > -1).all())
        assert_((r <= 0).all())

    def test_uniform_array(self):
        r = self.rg.uniform(np.array([-1.0] * 10), 0.0, size=10)
        assert_(len(r) == 10)
        assert_((r > -1).all())
        assert_((r <= 0).all())
        r = self.rg.uniform(np.array([-1.0] * 10), np.array([0.0] * 10), size=10)
        assert_(len(r) == 10)
        assert_((r > -1).all())
        assert_((r <= 0).all())
        r = self.rg.uniform(-1.0, np.array([0.0] * 10), size=10)
        assert_(len(r) == 10)
        assert_((r > -1).all())
        assert_((r <= 0).all())

    def test_random(self):
        assert_(len(self.rg.random(10)) == 10)
        params_0(self.rg.random)

    def test_standard_normal_zig(self):
        assert_(len(self.rg.standard_normal(10)) == 10)

    def test_standard_normal(self):
        assert_(len(self.rg.standard_normal(10)) == 10)
        params_0(self.rg.standard_normal)

    def test_standard_gamma(self):
        assert_(len(self.rg.standard_gamma(10, 10)) == 10)
        assert_(len(self.rg.standard_gamma(np.array([10] * 10), 10)) == 10)
        params_1(self.rg.standard_gamma)

    def test_standard_exponential(self):
        assert_(len(self.rg.standard_exponential(10)) == 10)
        params_0(self.rg.standard_exponential)

    def test_standard_exponential_float(self):
        randoms = self.rg.standard_exponential(10, dtype="float32")
        assert_(len(randoms) == 10)
        assert randoms.dtype == np.float32
        params_0(partial(self.rg.standard_exponential, dtype="float32"))

    def test_standard_exponential_float_log(self):
        randoms = self.rg.standard_exponential(10, dtype="float32", method="inv")
        assert_(len(randoms) == 10)
        assert randoms.dtype == np.float32
        params_0(partial(self.rg.standard_exponential, dtype="float32", method="inv"))

    def test_standard_cauchy(self):
        assert_(len(self.rg.standard_cauchy(10)) == 10)
        params_0(self.rg.standard_cauchy)

    def test_standard_t(self):
        assert_(len(self.rg.standard_t(10, 10)) == 10)
        params_1(self.rg.standard_t)

    def test_binomial(self):
        assert_(self.rg.binomial(10, 0.5) >= 0)
        assert_(self.rg.binomial(1000, 0.5) >= 0)

    def test_reset_state(self):
        state = self.rg.bit_generator.state
        int_1 = self.rg.integers(2**31)
        self.rg.bit_generator.state = state
        int_2 = self.rg.integers(2**31)
        assert_(int_1 == int_2)
        with pytest.raises(TypeError):
            self.rg.bit_generator.state = [(k, v) for k, v in state.items()]
        with pytest.raises(ValueError):
            wrong_state = state.copy()
            wrong_state["bit_generator"] = "WrongClass"
            self.rg.bit_generator.state = wrong_state

    def test_entropy_init(self):
        rg = self.init_generator()
        rg2 = self.init_generator()
        assert_(not comp_state(rg.bit_generator.state, rg2.bit_generator.state))

    def test_seed(self):
        rg = self.init_generator(self.seed, mode="legacy")
        rg2 = self.init_generator(self.seed, mode="legacy")
        assert_(comp_state(rg.bit_generator.state, rg2.bit_generator.state))
        rg.random()
        rg2.random()
        assert_(comp_state(rg.bit_generator.state, rg2.bit_generator.state))

    def test_reset_state_gauss(self):
        rg = self.init_generator(seed=self.seed, mode="legacy")
        rg.standard_normal()
        state = rg.bit_generator.state
        n1 = rg.standard_normal(size=10)
        rg2 = self.init_generator()
        rg2.bit_generator.state = state
        n2 = rg2.standard_normal(size=10)
        assert_array_equal(n1, n2)

    def test_reset_state_uint32(self):
        rg = self.init_generator(seed=self.seed, mode="legacy")
        rg.integers(0, 2**24, 120, dtype=np.uint32)
        state = rg.bit_generator.state
        n1 = rg.integers(0, 2**24, 10, dtype=np.uint32)
        rg2 = self.init_generator()
        rg2.bit_generator.state = state
        n2 = rg2.integers(0, 2**24, 10, dtype=np.uint32)
        assert_array_equal(n1, n2)

    def test_reset_state_float(self):
        rg = self.init_generator(seed=self.seed, mode="legacy")
        rg.random(dtype="float32")
        state = rg.bit_generator.state
        n1 = rg.random(size=10, dtype="float32")
        rg2 = self.init_generator()
        rg2.bit_generator.state = state
        n2 = rg2.random(size=10, dtype="float32")
        assert_((n1 == n2).all())

    def test_shuffle(self):
        original = np.arange(200, 0, -1)
        permuted = self.rg.permutation(original)
        assert_((original != permuted).any())

    def test_permutation(self):
        original = np.arange(200, 0, -1)
        permuted = self.rg.permutation(original)
        assert_((original != permuted).any())

    def test_beta(self):
        vals = self.rg.beta(2.0, 2.0, 10)
        assert_(len(vals) == 10)
        vals = self.rg.beta(np.array([2.0] * 10), 2.0)
        assert_(len(vals) == 10)
        vals = self.rg.beta(2.0, np.array([2.0] * 10))
        assert_(len(vals) == 10)
        vals = self.rg.beta(np.array([2.0] * 10), np.array([2.0] * 10))
        assert_(len(vals) == 10)
        vals = self.rg.beta(np.array([2.0] * 10), np.array([[2.0]] * 10))
        assert_(vals.shape == (10, 10))

    def test_bytes(self):
        vals = self.rg.bytes(10)
        assert_(len(vals) == 10)

    def test_chisquare(self):
        vals = self.rg.chisquare(2.0, 10)
        assert_(len(vals) == 10)
        params_1(self.rg.chisquare)

    def test_exponential(self):
        vals = self.rg.exponential(2.0, 10)
        assert_(len(vals) == 10)
        params_1(self.rg.exponential)

    def test_f(self):
        vals = self.rg.f(3, 1000, 10)
        assert_(len(vals) == 10)

    def test_gamma(self):
        vals = self.rg.gamma(3, 2, 10)
        assert_(len(vals) == 10)

    def test_geometric(self):
        vals = self.rg.geometric(0.5, 10)
        assert_(len(vals) == 10)
        params_1(self.rg.exponential, bounded=True)

    def test_gumbel(self):
        vals = self.rg.gumbel(2.0, 2.0, 10)
        assert_(len(vals) == 10)

    def test_laplace(self):
        vals = self.rg.laplace(2.0, 2.0, 10)
        assert_(len(vals) == 10)

    def test_logitic(self):
        vals = self.rg.logistic(2.0, 2.0, 10)
        assert_(len(vals) == 10)

    def test_logseries(self):
        vals = self.rg.logseries(0.5, 10)
        assert_(len(vals) == 10)

    def test_negative_binomial(self):
        vals = self.rg.negative_binomial(10, 0.2, 10)
        assert_(len(vals) == 10)

    def test_noncentral_chisquare(self):
        vals = self.rg.noncentral_chisquare(10, 2, 10)
        assert_(len(vals) == 10)

    def test_noncentral_f(self):
        vals = self.rg.noncentral_f(3, 1000, 2, 10)
        assert_(len(vals) == 10)
        vals = self.rg.noncentral_f(np.array([3] * 10), 1000, 2)
        assert_(len(vals) == 10)
        vals = self.rg.noncentral_f(3, np.array([1000] * 10), 2)
        assert_(len(vals) == 10)
        vals = self.rg.noncentral_f(3, 1000, np.array([2] * 10))
        assert_(len(vals) == 10)

    def test_normal(self):
        vals = self.rg.normal(10, 0.2, 10)
        assert_(len(vals) == 10)

    def test_pareto(self):
        vals = self.rg.pareto(3.0, 10)
        assert_(len(vals) == 10)

    def test_poisson(self):
        vals = self.rg.poisson(10, 10)
        assert_(len(vals) == 10)
        vals = self.rg.poisson(np.array([10] * 10))
        assert_(len(vals) == 10)
        params_1(self.rg.poisson)

    def test_power(self):
        vals = self.rg.power(0.2, 10)
        assert_(len(vals) == 10)

    def test_integers(self):
        vals = self.rg.integers(10, 20, 10)
        assert_(len(vals) == 10)

    def test_random_integers(self):
        with suppress_warnings() as sup:
            sup.record(DeprecationWarning)
            vals = self.rg.integers(10, 20, 10)
        assert_(len(vals) == 10)

    def test_rayleigh(self):
        vals = self.rg.rayleigh(0.2, 10)
        assert_(len(vals) == 10)
        params_1(self.rg.rayleigh, bounded=True)

    def test_vonmises(self):
        vals = self.rg.vonmises(10, 0.2, 10)
        assert_(len(vals) == 10)

    def test_wald(self):
        vals = self.rg.wald(1.0, 1.0, 10)
        assert_(len(vals) == 10)

    def test_weibull(self):
        vals = self.rg.weibull(1.0, 10)
        assert_(len(vals) == 10)

    def test_zipf(self):
        vals = self.rg.zipf(10, 10)
        assert_(len(vals) == 10)
        vals = self.rg.zipf(self.vec_1d)
        assert_(len(vals) == 100)
        vals = self.rg.zipf(self.vec_2d)
        assert_(vals.shape == (1, 100))
        vals = self.rg.zipf(self.mat)
        assert_(vals.shape == (100, 100))

    def test_hypergeometric(self):
        vals = self.rg.hypergeometric(25, 25, 20)
        assert_(np.isscalar(vals))
        vals = self.rg.hypergeometric(np.array([25] * 10), 25, 20)
        assert_(vals.shape == (10,))

    def test_triangular(self):
        vals = self.rg.triangular(-5, 0, 5)
        assert_(np.isscalar(vals))
        vals = self.rg.triangular(-5, np.array([0] * 10), 5)
        assert_(vals.shape == (10,))

    def test_multivariate_normal(self):
        mean = [0, 0]
        cov = [[1, 0], [0, 100]]  # diagonal covariance
        x = self.rg.multivariate_normal(mean, cov, 5000)
        assert_(x.shape == (5000, 2))
        x_zig = self.rg.multivariate_normal(mean, cov, 5000)
        assert_(x.shape == (5000, 2))
        x_inv = self.rg.multivariate_normal(mean, cov, 5000)
        assert_(x.shape == (5000, 2))
        assert_((x_zig != x_inv).any())

    def test_multinomial(self):
        vals = self.rg.multinomial(100, [1.0 / 3, 2.0 / 3])
        assert_(vals.shape == (2,))
        vals = self.rg.multinomial(100, [1.0 / 3, 2.0 / 3], size=10)
        assert_(vals.shape == (10, 2))

    def test_dirichlet(self):
        s = self.rg.dirichlet((10, 5, 3), 20)
        assert_(s.shape == (20, 3))

    @pytest.mark.skip(reason="Doesn't work since can't register bit generators")
    def test_pickle(self):
        pick = pickle.dumps(self.rg)
        unpick = pickle.loads(pick)
        assert type(self.rg) == type(unpick)
        assert comp_state(self.rg.bit_generator.state, unpick.bit_generator.state)

        pick = pickle.dumps(self.rg)
        unpick = pickle.loads(pick)
        assert type(self.rg) == type(unpick)
        assert comp_state(self.rg.bit_generator.state, unpick.bit_generator.state)

    def test_seed_array(self):
        if self.seed_vector_bits is None:
            if isinstance(self.bit_generator, partial):
                bit_gen_name = self.bit_generator.func.__name__
            else:
                bit_gen_name = self.bit_generator.__name__
            pytest.skip("Vector seeding is not supported by {0}".format(bit_gen_name))

        dtype = np.uint32 if self.seed_vector_bits == 32 else np.uint64
        seed = np.array([1], dtype=dtype)
        self.rg.bit_generator.seed(seed)
        state1 = self.rg.bit_generator.state
        self.rg.bit_generator.seed(1)
        state2 = self.rg.bit_generator.state
        assert_(comp_state(state1, state2))

    def test_array_scalar_seed_diff(self):
        if self.max_vector_seed_size == 1:
            pytest.skip("Skipping since max_vector_seed_size is 1")
        dtype = np.uint32 if self.seed_vector_bits == 32 else np.uint64
        seed = np.arange(3, 3 + self.max_vector_seed_size, dtype=dtype)
        self.rg.bit_generator.seed(seed)
        state1 = self.rg.bit_generator.state
        self.rg.bit_generator.seed(seed[0])
        state2 = self.rg.bit_generator.state
        assert_(not comp_state(state1, state2))

        seed = np.arange(1, 1 + self.max_vector_seed_size, dtype=dtype)
        self.rg.bit_generator.seed(seed)
        state1 = self.rg.bit_generator.state
        self.rg.bit_generator.seed(seed[0])
        state2 = self.rg.bit_generator.state
        assert_(not comp_state(state1, state2))

        seed = (
            2
            ** np.mod(
                np.arange(1500, 1500 + self.max_vector_seed_size, dtype=dtype),
                self.seed_vector_bits - 1,
            )
            + 1
        )
        self.rg.bit_generator.seed(seed)
        state1 = self.rg.bit_generator.state
        self.rg.bit_generator.seed(seed[0])
        state2 = self.rg.bit_generator.state
        assert_(not comp_state(state1, state2))

    def test_seed_array_error(self):
        if self.seed_vector_bits == 32:
            out_of_bounds = 2**32
        else:
            out_of_bounds = 2**64

        seed = -1
        with pytest.raises(ValueError):
            self.rg.bit_generator.seed(seed)

        seed = np.array([-1], dtype=np.int32)
        with pytest.raises((ValueError, TypeError)):
            self.rg.bit_generator.seed(seed)

        seed = np.array([1, 2, 3, -5], dtype=np.int32)
        with pytest.raises((ValueError, TypeError)):
            self.rg.bit_generator.seed(seed)

        skip = (LXM, LCG128Mix, PCG64DXSM, EFIIX64, Romu)
        if isinstance(self.rg.bit_generator, skip):
            return
        seed = np.array([1, 2, 3, out_of_bounds])
        with pytest.raises((ValueError, TypeError)):
            self.rg.bit_generator.seed(seed)

    def test_uniform_float(self):
        rg = self.init_generator(seed=[12345], mode="legacy")
        warmup(rg)
        state = rg.bit_generator.state
        r1 = rg.random(11, dtype=np.float32)
        rg2 = self.init_generator()
        warmup(rg2)
        rg2.bit_generator.state = state
        r2 = rg2.random(11, dtype=np.float32)
        assert_array_equal(r1, r2)
        assert_equal(r1.dtype, np.float32)
        assert_(comp_state(rg.bit_generator.state, rg2.bit_generator.state))

    def test_gamma_floats(self):
        rg = self.init_generator()
        warmup(rg)
        state = rg.bit_generator.state
        r1 = rg.standard_gamma(4.0, 11, dtype=np.float32)
        rg2 = self.init_generator(mode="legacy")
        warmup(rg2)
        rg2.bit_generator.state = state
        r2 = rg2.standard_gamma(4.0, 11, dtype=np.float32)
        assert_array_equal(r1, r2)
        assert_equal(r1.dtype, np.float32)
        assert_(comp_state(rg.bit_generator.state, rg2.bit_generator.state))

    def test_normal_floats(self):
        rg = self.init_generator(mode="legacy")
        warmup(rg)
        state = rg.bit_generator.state
        r1 = rg.standard_normal(11, dtype=np.float32)
        rg2 = self.init_generator()
        warmup(rg2)
        rg2.bit_generator.state = state
        r2 = rg2.standard_normal(11, dtype=np.float32)
        assert_array_equal(r1, r2)
        assert_equal(r1.dtype, np.float32)
        assert_(comp_state(rg.bit_generator.state, rg2.bit_generator.state))

    def test_normal_zig_floats(self):
        rg = self.init_generator()
        warmup(rg)
        state = rg.bit_generator.state
        r1 = rg.standard_normal(11, dtype=np.float32)
        rg2 = self.init_generator(mode="legacy")
        warmup(rg2)
        rg2.bit_generator.state = state
        r2 = rg2.standard_normal(11, dtype=np.float32)
        assert_array_equal(r1, r2)
        assert_equal(r1.dtype, np.float32)
        assert_(comp_state(rg.bit_generator.state, rg2.bit_generator.state))

    def test_output_fill(self):
        rg = self.rg
        state = rg.bit_generator.state
        size = (31, 7, 97)
        existing = np.empty(size)
        rg.bit_generator.state = state
        rg.standard_normal(out=existing)
        rg.bit_generator.state = state
        direct = rg.standard_normal(size=size)
        assert_equal(direct, existing)

        sized = np.empty(size)
        rg.bit_generator.state = state
        rg.standard_normal(out=sized, size=sized.shape)

        existing = np.empty(size, dtype=np.float32)
        rg.bit_generator.state = state
        rg.standard_normal(out=existing, dtype=np.float32)
        rg.bit_generator.state = state
        direct = rg.standard_normal(size=size, dtype=np.float32)
        assert_equal(direct, existing)

    def test_output_filling_uniform(self):
        rg = self.rg
        state = rg.bit_generator.state
        size = (31, 7, 97)
        existing = np.empty(size)
        rg.bit_generator.state = state
        rg.random(out=existing)
        rg.bit_generator.state = state
        direct = rg.random(size=size)
        assert_equal(direct, existing)

        existing = np.empty(size, dtype=np.float32)
        rg.bit_generator.state = state
        rg.random(out=existing, dtype=np.float32)
        rg.bit_generator.state = state
        direct = rg.random(size=size, dtype=np.float32)
        assert_equal(direct, existing)

    def test_output_filling_exponential(self):
        rg = self.rg
        state = rg.bit_generator.state
        size = (31, 7, 97)
        existing = np.empty(size)
        rg.bit_generator.state = state
        rg.standard_exponential(out=existing)
        rg.bit_generator.state = state
        direct = rg.standard_exponential(size=size)
        assert_equal(direct, existing)

        existing = np.empty(size, dtype=np.float32)
        rg.bit_generator.state = state
        rg.standard_exponential(out=existing, dtype=np.float32)
        rg.bit_generator.state = state
        direct = rg.standard_exponential(size=size, dtype=np.float32)
        assert_equal(direct, existing)

    def test_output_filling_gamma(self):
        rg = self.rg
        state = rg.bit_generator.state
        size = (31, 7, 97)
        existing = np.zeros(size)
        rg.bit_generator.state = state
        rg.standard_gamma(1.0, out=existing)
        rg.bit_generator.state = state
        direct = rg.standard_gamma(1.0, size=size)
        assert_equal(direct, existing)

        existing = np.zeros(size, dtype=np.float32)
        rg.bit_generator.state = state
        rg.standard_gamma(1.0, out=existing, dtype=np.float32)
        rg.bit_generator.state = state
        direct = rg.standard_gamma(1.0, size=size, dtype=np.float32)
        assert_equal(direct, existing)

    def test_output_filling_gamma_broadcast(self):
        rg = self.rg
        state = rg.bit_generator.state
        size = (31, 7, 97)
        mu = np.arange(97.0) + 1.0
        existing = np.zeros(size)
        rg.bit_generator.state = state
        rg.standard_gamma(mu, out=existing)
        rg.bit_generator.state = state
        direct = rg.standard_gamma(mu, size=size)
        assert_equal(direct, existing)

        existing = np.zeros(size, dtype=np.float32)
        rg.bit_generator.state = state
        rg.standard_gamma(mu, out=existing, dtype=np.float32)
        rg.bit_generator.state = state
        direct = rg.standard_gamma(mu, size=size, dtype=np.float32)
        assert_equal(direct, existing)

    def test_output_fill_error(self):
        rg = self.rg
        size = (31, 7, 97)
        existing = np.empty(size)
        with pytest.raises(TypeError):
            rg.standard_normal(out=existing, dtype=np.float32)
        with pytest.raises(ValueError):
            rg.standard_normal(out=existing[::3])
        existing = np.empty(size, dtype=np.float32)
        with pytest.raises(TypeError):
            rg.standard_normal(out=existing, dtype=np.float64)

        existing = np.zeros(size, dtype=np.float32)
        with pytest.raises(TypeError):
            rg.standard_gamma(1.0, out=existing, dtype=np.float64)
        with pytest.raises(ValueError):
            rg.standard_gamma(1.0, out=existing[::3], dtype=np.float32)
        existing = np.zeros(size, dtype=np.float64)
        with pytest.raises(TypeError):
            rg.standard_gamma(1.0, out=existing, dtype=np.float32)
        with pytest.raises(ValueError):
            rg.standard_gamma(1.0, out=existing[::3])

    def test_integers_broadcast(self, dtype):
        if dtype == bool:
            upper = 2
            lower = 0
        else:
            info = np.iinfo(dtype)
            upper = int(info.max) + 1
            lower = info.min
        self._reset_state()
        a = self.rg.integers(lower, [upper] * 10, dtype=dtype)
        self._reset_state()
        b = self.rg.integers([lower] * 10, upper, dtype=dtype)
        assert_equal(a, b)
        self._reset_state()
        c = self.rg.integers(lower, upper, size=10, dtype=dtype)
        assert_equal(a, c)
        self._reset_state()
        d = self.rg.integers(
            np.array([lower] * 10),
            np.array([upper], dtype=object),
            size=10,
            dtype=dtype,
        )
        assert_equal(a, d)
        self._reset_state()
        e = self.rg.integers(
            np.array([lower] * 10), np.array([upper] * 10), size=10, dtype=dtype
        )
        assert_equal(a, e)

        self._reset_state()
        a = self.rg.integers(0, upper, size=10, dtype=dtype)
        self._reset_state()
        b = self.rg.integers([upper] * 10, dtype=dtype)
        assert_equal(a, b)

    def test_integers_numpy(self, dtype):
        high = np.array([1])
        low = np.array([0])

        out = self.rg.integers(low, high, dtype=dtype)
        assert out.shape == (1,)

        out = self.rg.integers(low[0], high, dtype=dtype)
        assert out.shape == (1,)

        out = self.rg.integers(low, high[0], dtype=dtype)
        assert out.shape == (1,)

    def test_integers_broadcast_errors(self, dtype):
        if dtype == bool:
            upper = 2
            lower = 0
        else:
            info = np.iinfo(dtype)
            upper = int(info.max) + 1
            lower = info.min
        with pytest.raises(ValueError):
            self.rg.integers(lower, [upper + 1] * 10, dtype=dtype)
        with pytest.raises(ValueError):
            self.rg.integers(lower - 1, [upper] * 10, dtype=dtype)
        with pytest.raises(ValueError):
            self.rg.integers([lower - 1], [upper] * 10, dtype=dtype)
        with pytest.raises(ValueError):
            self.rg.integers([0], [0], dtype=dtype)

    def test_bit_generator_raw_large(self):
        bg = self.rg.bit_generator
        state = bg.state
        raw = bg.random_raw(100000)
        bg.state = state
        assert_equal(raw, bg.random_raw(100000))

    def test_bit_generator_raw(self):
        bg = self.rg.bit_generator
        val = bg.random_raw()
        assert np.isscalar(val)
        val = bg.random_raw(1)
        assert val.shape == (1,)
        val = bg.random_raw(1000)
        assert val.shape == (1000,)
        assert val.dtype == np.uint64

    def test_bit_generator_benchmark(self):
        bg = self.rg.bit_generator
        state = bg.state
        bg._benchmark(1000)
        assert not comp_state(state, bg.state)
        state = bg.state
        bg._benchmark(1000, "double")
        assert not comp_state(state, bg.state)


class TestMT19937(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = MT19937
        cls.advance = None
        cls.seed = [2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 32
        cls._extra_setup()
        cls.seed_error = ValueError

    def test_numpy_state(self):
        nprg = np.random.RandomState()
        nprg.standard_normal(99)
        state = nprg.get_state()
        self.rg.bit_generator.state = state
        state2 = self.rg.bit_generator.state
        assert_((state[1] == state2["state"]["key"]).all())
        assert_((state[2] == state2["state"]["pos"]))


class TestMT64(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = MT64
        cls.advance = None
        cls.seed = [2**43 + 2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError


class TestJSF64(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = partial(JSF, seed_size=3)
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestJSF32(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = partial(JSF, size=32, seed_size=3)
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestPCG64(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = PCG64
        cls.advance = 2**96 + 2**48 + 2**21 + 2**16 + 2**5 + 1
        cls.seed = [
            2**96 + 2**48 + 2**21 + 2**16 + 2**5 + 1,
            2**21 + 2**16 + 2**5 + 1,
        ]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = None
        cls._extra_setup()

    def test_seed_array_error(self):
        # GH #82 for error type changes
        if self.seed_vector_bits == 32:
            out_of_bounds = 2**32
        else:
            out_of_bounds = 2**64

        seed = -1
        with pytest.raises(ValueError):
            self.rg.bit_generator.seed(seed)

        error_type = ValueError if self.seed_vector_bits else TypeError
        seed = np.array([-1], dtype=np.int32)
        with pytest.raises(error_type):
            self.rg.bit_generator.seed(seed)

        seed = np.array([1, 2, 3, -5], dtype=np.int32)
        with pytest.raises(error_type):
            self.rg.bit_generator.seed(seed)

        seed = np.array([1, 2, 3, out_of_bounds])
        with pytest.raises(error_type):
            self.rg.bit_generator.seed(seed)

    def test_array_scalar_seed_diff(self):
        pass


class TestPCG64VariantDXSM(TestPCG64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = partial(PCG64, variant="dxsm-128")
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls._extra_setup()


class TestPCG64CMDXSM(TestPCG64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = partial(PCG64, variant="dxsm")
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls._extra_setup()


class TestPhilox4x64(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.number = 4
        cls.width = 64
        cls.bit_generator_base = Philox
        cls.bit_generator = partial(Philox, number=cls.number, width=cls.width)
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls.max_vector_seed_size = 1
        cls._extra_setup()

    def test_repr(self):
        rpr = repr(self.bit_generator(mode="sequence"))
        assert "{0}x{1}".format(self.number, self.width) in rpr

    def test_bad_width_number(self):
        with pytest.raises(ValueError, match="number must be either 2 or 4"):
            self.bit_generator_base(number=self.number + 1, mode="legacy")
        with pytest.raises(ValueError, match="width must be either 32 or 64"):
            self.bit_generator_base(width=self.width - 1, mode="legacy")


class TestPhilox2x64(TestPhilox4x64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.number = 2
        cls.width = 64
        cls.bit_generator = partial(Philox, number=cls.number, width=cls.width)
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls.max_vector_seed_size = 1
        cls._extra_setup()


class TestPhilox2x32(TestPhilox4x64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.number = 2
        cls.width = 32
        cls.bit_generator = partial(Philox, number=cls.number, width=cls.width)
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestPhilox4x32(TestPhilox4x64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.number = 4
        cls.width = 32
        cls.bit_generator = partial(Philox, number=cls.number, width=cls.width)
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestThreeFry4x64(TestPhilox4x64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.number = 4
        cls.width = 64
        cls.bit_generator_base = ThreeFry
        cls.bit_generator = partial(ThreeFry, number=cls.number, width=cls.width)
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestThreeFry2x64(TestPhilox4x64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.number = 2
        cls.width = 64
        cls.bit_generator = partial(ThreeFry, number=cls.number, width=cls.width)
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestThreeFry2x32(TestPhilox4x64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.number = 2
        cls.width = 32
        cls.bit_generator = partial(ThreeFry, number=cls.number, width=cls.width)
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestThreeFry4x32(TestPhilox4x64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.number = 4
        cls.width = 32
        cls.bit_generator = partial(ThreeFry, number=cls.number, width=cls.width)
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestXoroshiro128(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = Xoroshiro128
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestXoroshiro128PlusPlus(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = partial(Xoroshiro128, plusplus=True)
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls._extra_setup()


class TestXoshiro256(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = Xoshiro256
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestXoshiro512(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = Xoshiro512
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestXorshift1024(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = Xorshift1024
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()


class TestDSFMT(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = DSFMT
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls._extra_setup()
        cls.seed_vector_bits = 32


class TestSFMT(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = SFMT
        cls.advance = None
        cls.seed = [12345]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls._extra_setup()
        cls.seed_vector_bits = 32


class TestEntropy(object):
    def test_entropy(self):
        e1 = entropy.random_entropy()
        e2 = entropy.random_entropy()
        assert_((e1 != e2))
        e1 = entropy.random_entropy(10)
        e2 = entropy.random_entropy(10)
        assert_((e1 != e2).all())
        e1 = entropy.random_entropy(10, source="system")
        e2 = entropy.random_entropy(10, source="system")
        assert_((e1 != e2).all())

    def test_fallback(self):
        e1 = entropy.random_entropy(source="fallback")
        time.sleep(0.1)
        e2 = entropy.random_entropy(source="fallback")
        assert_((e1 != e2))


class TestPCG32(TestPCG64):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = PCG32
        cls.advance = 2**48 + 2**21 + 2**16 + 2**5 + 1
        cls.seed = [
            2**48 + 2**21 + 2**16 + 2**5 + 1,
            2**21 + 2**16 + 2**5 + 1,
        ]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = None
        cls._extra_setup()


class TestAESCounter(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = AESCounter
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError
        cls.max_vector_seed_size = 2


class TestChaCha(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = ChaCha
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.seed = [2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError


class TestHC128(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = HC128
        cls.seed = [2**231 + 2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError


class TestSPECK128(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = SPECK128
        cls.seed = [2**231 + 2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed, mode="legacy"))
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError


class TestLXM(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = LXM
        cls.seed = [2**231 + 2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed))
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError
        cls.out_of_bounds = 2**192 + 1

    def init_generator(self, seed=None, mode="sequence"):
        return np.random.Generator(self.bit_generator(seed=seed))


class TestLCG128Mix(RNG):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = LCG128Mix
        cls.seed = [2**231 + 2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed))
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError
        cls.out_of_bounds = 2**192 + 1

    def init_generator(self, seed=None, mode="sequence"):
        return np.random.Generator(self.bit_generator(seed=seed))


class TestPCG64DXSM(TestLCG128Mix):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = PCG64DXSM
        cls.seed = [2**231 + 2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed))
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError
        cls.out_of_bounds = 2**192 + 1


class TestEFIIX64(TestLCG128Mix):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = EFIIX64
        cls.seed = [2**231 + 2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed))
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError
        cls.out_of_bounds = 2**192 + 1


class TestRomu(TestLCG128Mix):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        cls.bit_generator = Romu
        cls.seed = [2**231 + 2**21 + 2**16 + 2**5 + 1]
        cls.rg = np.random.Generator(cls.bit_generator(*cls.seed))
        cls.advance = 2**63 + 2**31 + 2**15 + 1
        cls.initial_state = cls.rg.bit_generator.state
        cls.seed_vector_bits = 64
        cls._extra_setup()
        cls.seed_error = ValueError
        cls.out_of_bounds = 2**192 + 1
