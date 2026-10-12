"""Capture-side text cache: resend before input, never wait for a UI read."""
class ClipboardState:
    def __init__(self):self.enabled=False;self.text=None
    def configure(self,enabled):
        self.enabled=bool(enabled)
        if not self.enabled:self.text=None
    def update(self,text):
        if self.enabled:self.text=text
    def sync(self,phone):
        if self.enabled and self.text is not None:phone.clipboard(self.text)
