
class VolumeModel:
    def __init__(self, journey, time_func=lambda t: 1, args_iterable=None, kwargs_iterable=None):
        self.journey = journey
        self.time_func = time_func
        self.args_iterable = args_iterable
        self.kwargs_iterable = kwargs_iterable