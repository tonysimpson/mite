from mite.exceptions import UnallocatableError


class RoundRobinAllocator:
    def __init__(self, vc):
        self.vc = vc

    def allocate(self):
        #TODO: Maybe more allocators if necessary
        pass


class FewestJobsAllocator:
    def __init__(self, vc):
        self.vc = vc

    def allocate(self):
        try:
            executors = filter(
                self.vc.executors().items(),
                lambda x: x[1][4] > 0 and x[0] not in self.vc.banned_executors
            )
            return min(executors, key=lambda x: x[1][4])[0]
        except ValueError:
            raise UnallocatableError(self)
