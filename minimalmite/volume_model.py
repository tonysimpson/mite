
class VolumeModel:
    def __init__(self, journey, action_identifier=None, time_func=lambda t: 1, args_iterable=None, kwargs_iterable=None):
        self.action_identifier = action_identifier or journey.__name__
        self.journey = journey
        self.time_func = time_func
        self.args_iterable = args_iterable
        self.kwargs_iterable = kwargs_iterable

    def current_required(self, time):
        return self.time_func(time)

    def __next__(self):
        self.action_identifier, self.journey.__name__, next(self.args_iterable), next(self.kwargs_iterable)

