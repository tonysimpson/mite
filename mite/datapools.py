from collections import namedtuple, deque
from itertools import count


DataPoolItem = namedtuple('DataPoolItem', 'id data'.split())


class DataPoolExhausted(BaseException):
    pass


class RecyclableIterableDataPool:
    def __init__(self, iterable):
        self._iter = iter(iterable)
        self._iterable_exhausted = False
        self._checked_out = {}
        self._available = deque()
        self._id_gen = count(1)

    def checkout(self):
        if not self._iterable_exhausted:
            try:
                data = next(self._iter)
            except StopIteration:
                self._iterable_exhausted = True
            else:
                id = next(self._id_gen)
                dpi = DataPoolItem(id, data)
                self._checked_out[id] = data
                return dpi
        if self._available:
            dpi = self._available.popleft()
            self._checked_out[dpi.id] = dpi.data
            return dpi
        else:
            return None

    def checkin(self, id):
        data = self._checked_out[id]
        self._available.append(DataPoolItem(id, data))


class IterableDataPool:
    def __init__(self, iterable):
        self._iter = iter(iterable)
        self._id_gen = count(1)

    def checkout(self):
        try:
            data = next(self._iter)
        except StopIteration:
            raise DataPoolExhausted()
        else:
            id = next(self._id_gen)
            dpi = DataPoolItem(id, data)
            return dpi
 
    def checkin(self, id):
        pass


def create_iterable_data_pool_with_recycling(iterable):
    return RecyclableIterableDataPool(iterable)


def create_iterable_data_pool(iterable):
    return IterableDataPool(iterable)

