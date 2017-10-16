

class MiteError(Exception):
    def __init__(self, message, **fields):
        super().__init__(message)
        self.fields = fields


class UnexpectedResponseCodeError(MiteError):
    def __init__(self, expected_code, resp):
        super().__init__("Expected HTTP response code of {}, returned code was {}".format(expected_code, resp.status_code),
        body=resp.body,
        status_code=resp.status_code,
        headers=resp.headers)


#TODO move to browser
class OptionError(MiteError):
    def __init__(self, value):
        super().__init__()
        self.message = "Attempted to set a value not in options".format(value)
