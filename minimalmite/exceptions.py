
class OptionError(Exception):
    def __init__(self, value):
        self.message = "Option: {} not in radio or select field".format(value)


class TestEnd(Exception):
    def __init__(self):
        pass


class RequestError(Exception):
    pass


class UnallocatableError(Exception):
    def __init__(self, allocator):
        self.message = "Allocator: {} can't allocate actions to executors".format(allocator)