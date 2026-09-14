import pytest

from mindcrafted.generator.world import compile_world
from mindcrafted.generator.world_demo import SOURCE, demo_blueprint


@pytest.fixture(scope="session")
def compiled_world():
    return compile_world(demo_blueprint(("route_network", "switch_sequence", "push_blocks")), SOURCE)


@pytest.fixture
def world_spec(compiled_world):
    from copy import deepcopy
    return deepcopy(compiled_world)
