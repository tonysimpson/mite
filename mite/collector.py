import time
import os
from itertools import count
import logging
from .utils import pack_msg


logger = logging.getLogger(__name__)


class Collector:
    def __init__(self, target_dir=None, roll_after_n_messages=10000):
        if target_dir is None:
            target_dir = 'collector_data'
        self._target_dir = os.path.abspath(target_dir)
        self._roll_after_n_messages = roll_after_n_messages
        try:
            os.makedirs(self._target_dir)
        except FileExistsError:
            pass
        self._file_counter = count()
        self._current_fn = os.path.join(self._target_dir, 'current')
        self._current_st_fn = os.path.join(self._target_dir, 'current_start_time')
        if os.path.isfile(self._current_fn):
            logger.debug('rotating pre-existing current file %s', self._current_fn)
            with open(self._current_st_fn) as f:
                start_time = f.read()
            end_time = int(time.time())
            c = next(self._file_counter)
            fn = os.path.join(self._target_dir, '%s_%s_%s' % (start_time, end_time, c))
            logger.warn('moving old current %s to %s', self._current_fn, fn)
            os.rename(self._current_fn, fn)
        with open(self._current_st_fn, 'w') as f:
            f.write(str(int(time.time())))
        self._current = open(self._current_fn, 'wb')
        self._msg_count = 0
        self._tps_start = time.time()
        self._tps_count = 0

    def process_raw_message(self, raw):
        self._msg_count += 1
        self._current.write(raw)
        if self._msg_count == self._roll_after_n_messages:
            self._msg_count = 0
            self._current.close()
            with open(self._current_st_fn) as f:
                start_time = f.read()
            end_time = int(time.time())
            c = next(self._file_counter)
            fn = os.path.join(self._target_dir, '%s_%s_%s' % (start_time, end_time, c))
            logger.info('moving current %s to %s', self._current_fn, fn)
            os.rename(self._current_fn, fn)
            with open(self._current_st_fn, 'w') as f:
                f.write(str(end_time))
            self._current = open(self._current_fn, 'wb')

    def process_message(self, msg):
        if 'type' in msg:
            if msg['type'] == 'data_created':
                open(os.path.join(self._target_dir, msg['name'] + '.msgpack'), 'ab').write(pack_msg(msg['data']))

        


        






