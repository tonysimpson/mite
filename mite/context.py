import importlib
import time
import traceback
from unittest.mock import MagicMock
from .exceptions import MiteError, HandledMiteError



class _TransactionContextManager:
    def __init__(self, ctx, name, debug):
        self._ctx = ctx
        self._name = name
        self._debug = debug

    def __enter__(self):
        self._ctx._start_transaction(self._name)

    def __exit__(self, exception_type, exception_val, traceback):
        if isinstance(exception_val, MiteError):
            self._ctx.send('error', message=str(exception_val), **exception_val.fields)
            self._ctx._end_transaction()
            if self._debug:
                import ipdb
                ipdb.post_mortem(traceback)
            raise HandledMiteError()
        self._ctx._end_transaction()


class Context:
    def __init__(self, send, config, id_data=None, should_stop_func=None, debug=False):
        self._send = send
        self._config = config
        if id_data is None:
            id_data = {}
        self._id_data = id_data
        self._should_stop_func = should_stop_func
        self._transaction_names = []
        self._debug = debug

    @property
    def config(self):
        return self._config

    @property
    def should_stop(self):
        if self._should_stop_func is not None:
            return self._should_stop_func()
        return False

    @property
    def _transaction_name(self):
        if self._transaction_names:
            return self._transaction_names[-1]
        else:
            return ''
    
    def _add_context_headers(self, msg):
        msg.update(self._id_data)
        msg['transaction'] = self._transaction_name

    def _add_context_headers_and_time(self, msg):
        self._add_context_headers(msg)
        msg['time'] = time.time()

    def _error(self, stacktrace):
        msg = {
            'stacktrace': stacktrace,
            'type': 'exception'
        }
        self._add_context_headers_and_time(msg)
        self._send(msg)

    def _start_transaction(self, name):
        msg = {}
        self._transaction_names.append(name)
        self._add_context_headers_and_time(msg)
        msg['type'] = 'start'
        self._send(msg)

    def _end_transaction(self):
        msg= {}
        self._add_context_headers_and_time(msg)
        msg['type'] = 'end'
        self._send(msg)
        name = self._transaction_names.pop()

    def send(self, type, **content):
        msg = content
        msg['type'] = type
        self._add_context_headers_and_time(msg)
        self._send(msg)

    def log_error(self):
        self._error(traceback.format_exc())

    def transaction(self, name):
        return _TransactionContextManager(self, name, self._debug)

