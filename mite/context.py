import importlib
import time
import traceback
from unittest.mock import MagicMock


class _TransactionContextManager:
    def __init__(self, user_session, name):
        self._user_session = user_session
        self._name = name

    def __enter__(self):
        self._user_session._start_transaction(self._name)

    def __exit__(self, *args):
        self._user_session._end_transaction()


class Context:
    def __init__(self, send, config, id_data=None):
        self._send = send
        self._config = config
        if id_data is None:
            id_data = {}
        self._id_data = id_data
        self._transaction_names = []
        self._cleanup_extensions = []

    @property
    def config(self):
        return self._config

    @property
    def _transaction_name(self):
        if self._transaction_names:
            return self._transaction_names[-1]
        else:
            return ''
    
    def attach_extension(self, name, checkout, checkin):
        self.__dict__[name] = checkout(self)
        if checkin is not None:
            self._cleanup_extensions.append((name, checkin))

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

    def __del__(self):
        for name, checkin in self._cleanup_extensions:
            checkin(getattr(self, name))

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
        return _TransactionContextManager(self, name)


def _extension_tree(extensions, loader):
    if extensions is None:
        return
    for ext in extensions:
        checkout, checkin, depends = loader(ext)
        yield ext, checkout, checkin, tuple(_extension_tree(depends, loader))


def _flatten_extension_tree(tree, current=None):
    if current is None:
        current = []
    for ext, checkout, checkin, extensions in tree:
        if extensions:
            _flatten_extension_tree(extensions, current)
        current.append((ext, checkout, checkin))
    return current


def _add_context_extensions(context, extensions, loader):
    seen = set()
    for ext, checkout, checkin in _flatten_extension_tree(_extension_tree(extensions, loader)):
        if ext not in seen:
            seen.add(ext)
            context.attach_extension(ext, checkout, checkin)


def _load_ext_module(ext):
    return importlib.import_module('mite_ctx_ext_{}'.format(ext))


def _ext_loader(extension):
    return _load_ext_module(extension).get_ext()


def _ext_mock_loader(extension):
    module = _load_ext_module(extension)
    if hasattr(module, 'get_ext_mock'):
        return module.get_ext_mock()
    else:
        _, _, depends = module.get_ext()
        # implementations of checkout, checkin and the real depends list
        return lambda ctx: MagicMock(), lambda x: None, depends


def add_context_extensions(context, extensions, as_mock=False):
    return _add_context_extensions(context, extensions, _ext_mock_loader if as_mock else _ext_loader)

