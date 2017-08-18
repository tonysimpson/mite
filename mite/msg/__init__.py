from ..time import time as mite_time

_MSG_TYPE_INFO = 1
_MSG_TYPE_TIME = 2
_MSG_TYPE_CONTEXT = 3
_MSG_TYPE_MSG = 4

_MICROS_PER_SECOND = 1000000


def default_msg_time():
    return int(mite_time() * _MICROS_PER_SECOND)


class MsgOutStream:
    def __init__(self, src_id, send_func, msg_time_func=default_msg_time, cache_timeout=5*_MICROS_PER_SECOND):
        self._src_id = src_id
        self._start_time = msg_time_func()
        self._msg_time = msg_time_func
        self._send = send_func
        self._last_time = -1

    def _time(self):
        return self._msg_time() - self._start_time

    def new_context(self, labels_to_set, parent=None):
        pass

    def _contexts_needing_refreshing(context, time):
        cur = context
        result = []
        while cur is not None:
            if cur.update_time < time:
                result.append(cur)
            cur = cur.parent
        result.reverse()
        return result

    def _send_contexts_if_needed(self, context, time):
        for ctx in self._contextS_needing_refreshing(context, time):
            ctx.update_time = time + self._cache_timeout_func(ctx)
            self._send([_MSG_TYPE_CONTEXT, self._src_id, context.id, 
                0 if context.parent is None else context.parent.id,
                context.update_time, context.labels])

    def _send_info_if_needed(self, time):
        if time - self._last_time > self._cache_timeout:
            self._send([_MSG_TYPE_INFO, self._src_id, self._start_time])
        
    def _send_time_and_update_if_needed(self, time):
        if self._last_time < time:
            self._send([_MSG_TYPE_TIME, self._src_id, time])
            self._last_time = time

    def send_message(self, context, type, data):
        time = self._time()
        self._send_info_if_needed(time)
        self._send_time_and_update_if_needed(time)
        self._send_contexts_if_needed(context, time)
        self._send([_MSG_TYPE_MSG, self._src_id, context.id, type, data])

class MsgInStream:
    def __init__(self, recv_func):

