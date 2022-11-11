from typing import Dict, Optional, Union

from randomgen.common import BitGenerator
from randomgen.typing import IntegerSequenceSeed, Literal, SeedMode

DEFAULT_MULTIPLIER: int
DEFAULT_DXSM_MULTIPLIER: int

class PCG64(BitGenerator):
    def __init__(
        self,
        seed: Optional[IntegerSequenceSeed] = ...,
        inc: Optional[int] = ...,
        *,
        variant: Literal[
            "xsl-rr", "1.0", 1, "dxsm", "cm-dxsm", 2, "2.0", "dxsm-128"
        ] = ...,
        mode: Optional[SeedMode] = ...
    ) -> None: ...
    def seed(
        self, seed: Optional[IntegerSequenceSeed] = ..., inc: Optional[int] = ...
    ) -> None: ...
    @property
    def state(self) -> Dict[str, Union[str, int, Dict[str, int]]]: ...
    @state.setter
    def state(self, value: Dict[str, Union[str, int, Dict[str, int]]]) -> None: ...
    def advance(self, delta: int) -> PCG64: ...
    def jump(self, iter: int = ...) -> PCG64: ...
    def jumped(self, iter: int = ...) -> PCG64: ...

class LCG128Mix(BitGenerator):
    def __init__(
        self,
        seed: Optional[IntegerSequenceSeed] = ...,
        inc: Optional[int] = ...,
        *,
        multiplier: int = ...,
        output: Union[str, int] = ...,
        dxsm_multiplier: int = ...,
        post: bool = ...
    ) -> None: ...
    def seed(
        self, seed: Optional[IntegerSequenceSeed] = ..., inc: Optional[int] = ...
    ) -> None: ...
    @property
    def state(self) -> Dict[str, Union[str, int, Dict[str, Union[bool, int, str]]]]: ...
    @state.setter
    def state(
        self, value: Dict[str, Union[str, int, Dict[str, Union[bool, int, str]]]]
    ) -> None: ...
    def advance(self, delta: int) -> LCG128Mix: ...
    def jumped(self, iter: int = ...) -> LCG128Mix: ...

class PCG64DXSM(PCG64):
    def __init__(
        self, seed: Optional[IntegerSequenceSeed] = ..., inc: Optional[int] = ...
    ) -> None: ...
    @property
    def state(self) -> Dict[str, Union[str, int, Dict[str, int]]]: ...
    @state.setter
    def state(self, value: Dict[str, Union[str, int, Dict[str, int]]]) -> None: ...
    def jumped(self, iter: int = ...) -> PCG64DXSM: ...
    def jump(self, iter: int = ...) -> PCG64DXSM: ...