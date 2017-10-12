from acurl import EventLoop

el = EventLoop()

def build(context):
    return el.session()

def get_ext():
    return build, None, None
