
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


class MiteException(Exception):
    def __init__(self):
        self.fields = {}


class UnexpectedResponseCodeError(MiteException):
    def __init__(self, expected_code, resp):
        super().__init__()
        self.message = "Expected HTTP response code of {}, returned code was {}".format(expected_code, resp.status_code)
        self.fields['body'] = resp.content
        self.fields['status_code'] = resp.status_code
        self.fields['headers'] = resp.headers


