from .browser import Browser


def add_mixin(context):
    context.browser = Browser(context.http)


def get_ext():
    return add_mixin, ['http']
