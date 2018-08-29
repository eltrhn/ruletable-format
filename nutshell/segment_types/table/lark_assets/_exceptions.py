class Reshape(Exception):
    def __init__(self, cdir):
        self.cdir = cdir


class Unpack(Exception):
    def __init__(self, index, value):
        self.idx = index
        self.val = value


class Special(Exception):
    def __init__(self, value):
        self.value = value