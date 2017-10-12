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


class OptionError(MiteException):
    def __init__(self, value):
        super().__init__()
        self.message = "Attempted to set a value not in options".format(value)
