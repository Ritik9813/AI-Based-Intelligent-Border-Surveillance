class Agent:
    """Base class. An agent reads a Track and returns a dict of named outputs.
    It may only return keys listed in `outputs` and use tools in the allow-list."""
    name = "agent"
    outputs = frozenset()

    def __init__(self):
        self.count = 0            # items processed (shown in the GUI)

    def process(self, track, ctx):
        raise NotImplementedError
