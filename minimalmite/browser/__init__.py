from minimalmite.browser.browser import Browser
from minimalmite.session import SessionController


class BrowserController(SessionController):
    """Thin wrapper around a Session controller, provides a method to spin up browsers."""
    def __init__(self):
        super().__init__()

    def create_new_browser(self, profile=None, metrics_callback=None):
        return Browser(self.create_new_session(profile=profile, metrics_callback=metrics_callback))
