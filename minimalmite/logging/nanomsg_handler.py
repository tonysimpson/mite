from logging import Handler, NOTSET, Filter
#from minimalmite.journey import send


class NanomsgHandler(Handler):
    def __init__(self, level=NOTSET):
        super().__init__(level=level)
        self.addFilter(NanomsgFilter())

    def emit(self, record):
        #import ipdb;
        #ipdb.set_trace()
        print("{} - NANOMSG_PLACEHOLDER".format(record.msg))


class NanomsgFilter(Filter):
    """Temporary filter, will be submitting issue to python to have filtering done by kwarg.
    This will allow log lines to be sent to the collector by doing something like """
    def __init__(self):
        super().__init__()

    def filter(self, record):
        return record.args
