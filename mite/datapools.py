from collections import namedtuple, deque
from itertools import count
import logging
import random
from .utils import spec_import


logger = logging.getLogger(__name__)


class DataPoolManager:
    def __init__(self, max_block_size=1000):
        self._max_block_size = max_block_size
        self._datapool_id_gen = count(1)
        self._spec_to_id = {}
        self._id_to_datapool = {}

    def register(self, datapool_spec):
        if datapool_spec is None:
            return 0
        if datapool_spec not in self._spec_to_id:
            datapool_id = next(self._datapool_id_gen)
            self._spec_to_id[datapool_spec] = datapool_id
            self._id_to_datapool[datapool_id] = spec_import(datapool_spec)
        return self._spec_to_id[datapool_spec]

    def checkin_block(self, datapool_id, ids):
        assert datapool_id > 0
        logger.debug('DataPoolManager.checkin_block datapool_id=%r ids=%r', datapool_id, ids)
        dp = self._id_to_datapool[datapool_id]
        for id in ids:
            dp.checkin(id)

    def checkout_block(self, datapool_id):
        assert datapool_id > 0
        result = []
        dp = self._id_to_datapool[datapool_id]
        block_size = random.randint(self._max_block_size // 10, self._max_block_size)
        for i in range(block_size):
            try:
                dpi = dp.checkout()
            except DataPoolExhausted:
                if not result:
                    return None
                break
            if dpi is None:
                break
            result.append(dpi)
        logger.debug('DataPoolManager.checkout_block datapool_id=%r result=%r', datapool_id, result)
        return result


DataPoolItem = namedtuple('DataPoolItem', 'id data'.split())


class DataPoolExhausted(BaseException):
    pass


class RecyclableIterableDataPool:
    def __init__(self, iterable):
        self._checked_out = {}
        self._available = deque(DataPoolItem(id, data) for id, data in enumerate(iterable, 1))

    def size(self):
        return len(self._checked_out) + len(self._available)

    def checkout(self):
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

    def size(self):
        return None

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

