from collections import OrderedDict
from timeit import repeat

import numpy as np
import pandas as pd

from randomgen import (DSFMT, MT64, MT19937, PCG64, SFMT, AESCounter, ChaCha,
                       Philox, ThreeFry, Xoshiro256, Xoshiro512, JSF, HC128,
                       SPECK128, RDRAND)


class JSF32(JSF):
    def __init__(self, *args, **kwargs):
        if 'size' in kwargs:
            del kwargs['size']
        super(JSF32, self).__init__(*args, size=32, **kwargs)


class Philox4x32(Philox):
    def __init__(self, *args, **kwargs):
        if 'width' in kwargs:
            del kwargs['width']
        super(Philox4x32, self).__init__(*args, width=32, **kwargs)


class Philox2x64(Philox):
    def __init__(self, *args, **kwargs):
        if 'number' in kwargs:
            del kwargs['number']
        super(Philox2x64, self).__init__(*args, number=2, **kwargs)


class ThreeFry4x32(ThreeFry):
    def __init__(self, *args, **kwargs):
        if 'width' in kwargs:
            del kwargs['width']
        super(ThreeFry4x32, self).__init__(*args, width=32, **kwargs)


class ThreeFry2x64(ThreeFry):
    def __init__(self, *args, **kwargs):
        if 'number' in kwargs:
            del kwargs['number']
        super(ThreeFry2x64, self).__init__(*args, number=2, **kwargs)


try:
    RDRAND()
    HAS_RDRND = True
except RuntimeError:
    HAS_RDRND = False

NUMBER = 100
REPEAT = 10
SIZE = 25000
PRNGS = [JSF32, Philox4x32, ThreeFry2x64, ThreeFry4x32, Philox2x64,
         DSFMT, MT64, MT19937, PCG64, SFMT, AESCounter, ChaCha, Philox,
         ThreeFry, Xoshiro256, Xoshiro512, JSF, HC128, SPECK128]

if HAS_RDRND:
    PRNGS.append(RDRAND)



funcs = OrderedDict()
funcs['Uint32'] = f'integers(2**32, dtype="uint32", size={SIZE})'
funcs['Uint64'] = f'integers(2**64, dtype="uint64", size={SIZE})'
funcs['Uniform'] = f'random(size={SIZE})'
funcs['Expon'] = f'standard_exponential(size={SIZE})'
funcs['Normal'] = f'standard_normal(size={SIZE})'
funcs['Gamma'] = f'standard_gamma(3.0,size={SIZE})'

setup = """
from randomgen import Generator
rg = Generator({prng}())
"""

test = "rg.{func}"
table = OrderedDict()
for prng in PRNGS:
    print(prng.__name__)
    print('-' * 40)
    col = OrderedDict()
    for key in funcs:
        print(key)
        t = repeat(test.format(func=funcs[key]),
                   setup.format(prng=prng().__class__.__name__),
                   number=NUMBER, repeat=REPEAT, globals=globals())
        col[key] = 1000 * min(t)
    print('\n' * 2)
    col = pd.Series(col)
    table[prng().__class__.__name__] = col

npfuncs = OrderedDict()
npfuncs.update(funcs)
npfuncs['Uniform'] = f'random_sample(size={SIZE})'
npfuncs['Uint64'] = f'randint(2**64, dtype="uint64", size={SIZE})'
npfuncs['Uint32'] = f'randint(2**32, dtype="uint32", size={SIZE})'


setup = """
from numpy.random import RandomState
rg = RandomState()
"""
col = {}
for key in npfuncs:
    t = repeat(test.format(func=npfuncs[key]),
               setup.format(prng=prng().__class__.__name__),
               number=NUMBER, repeat=REPEAT)
    col[key] = 1000 * min(t)
table['NumPy'] = pd.Series(col)
final = table

func_list = list(funcs.keys())
table = pd.DataFrame(final)
table = table.reindex(table.mean(1).sort_values().index)
order = np.log(table).mean().sort_values().index
table = table.T
table = table.reindex(order, axis=0)
table = table.reindex(func_list, axis=1)
table = 1000000 * table / (SIZE * NUMBER)
table.index.name = 'Bit Gen'
print(table.to_csv(float_format='%0.1f'))

try:
    from tabulate import tabulate

    perf = table.applymap(lambda v: '{0:0.1f}'.format(v))
    print(tabulate(perf, headers='keys', tablefmt='rst'))
except ImportError:
    pass

table = table.T
rel = table.loc[:, ['NumPy']].values @ np.ones((1, table.shape[1])) / table
rel.pop('NumPy')
rel = rel.T
rel['Overall'] = np.exp(np.log(rel).mean(1))
rel *= 100
rel = np.round(rel).astype(np.int)
rel.index.name = 'Bit Gen'
print(rel.to_csv(float_format='%0d'))

try:
    from tabulate import tabulate

    rel_perf = rel.applymap(lambda v: '{0:d}'.format(v))
    print(tabulate(rel_perf, headers='keys', tablefmt='rst'))
except ImportError:
    pass
