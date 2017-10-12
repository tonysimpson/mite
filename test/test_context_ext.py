from mite.context import Context, _add_context_extensions


class ContextT:
    _added = []
    def attach_extension(self, name, checkout, checkin):
        self._added.append(name)


def fake_loader(ext):
    if ext == 'wibble':
        return lambda ctx: True, lambda x: None, ['wobble', 'falldown']
    if ext == 'wobble':
        return lambda ctx: True, lambda x: None, ['falldown']
    if ext == 'falldown':
        return lambda ctx: True, lambda x: None, []


def test_attaching_ext():
    c = ContextT()
    _add_context_extensions(c, ['wibble'], fake_loader)
    assert c._added == ['falldown', 'wobble', 'wibble']


def test_with_real_context():
    c = Context(print, None, None)
    _add_context_extensions(c, ['wibble'], fake_loader)
    assert c.falldown
    assert c.wibble
    assert c.wobble
