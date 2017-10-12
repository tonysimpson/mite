import importlib

class _TransactionContextManager:
    def __init__(self, user_session, name):
        self._user_session = user_session
        self._name = name

    def __enter__(self):
        self._user_session._start_transaction(self._name)

    def __exit__(self, *args):
        self._user_session._end_transaction()


class Context:
    def __init__(self, send, config, data_pool_access, id_data=None):
        self._send = send
        self.config = config
        if id_data is None:
            id_data = {}
        self._id_data = id_data
        self._transaction_names = []

    @property
    def args(self):
        return []

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
        name = self._transaction_names.pop()
        self._add_context_headers_and_time(msg)
        msg['type'] = 'end'
        self._send(msg)

    def send_msg(self, type, content):
        msg = dict(content)
        msg['type'] = type;
        self._add_context_headers_and_time(msg)
        self._send(msg)

    def log_error(self):
        self._error(traceback.format_exc())

    def transaction(self, name):
        return _TransactionContextManager(self, name)


def _extension_tree(extensions):
    if extensions is None:
        return
    for ext in extensions:
        builder, depends = importlib.import_module('mite_ctx_ext_{}'.format(ext)).get_ext()
        yield ext, builder, tuple(_extension_tree(depends))


def _flatten_extension_tree(tree, current=None):
    if current is None:
        current = []
    for ext, builder, extensions in tree:
        if extensions:
            _flatten_extension_tree(extensions, current)
        current.append((ext, builder))
    return current


def add_context_extensions(context, extensions):
    seen = set()
    for ext, builder in _flatten_extension_tree(_extension_tree(extensions)):
        if ext not in seen:
            seen.add(ext)
            setattr(context, 'ext', builder(context))


    
