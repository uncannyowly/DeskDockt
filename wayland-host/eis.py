"""Small receiver-only ctypes binding to the installed libei and libxkbcommon."""
import ctypes as C
import os

P, I, U, D, B = C.c_void_p, C.c_int, C.c_uint32, C.c_double, C.c_bool

def bind(lib, name, result, *arguments):
    fn = getattr(lib, name)
    fn.restype = result
    fn.argtypes = list(arguments)
    return fn

class Receiver:
    def __init__(self, fd, callback):
        self.callback = callback
        self.e = C.CDLL('libei.so.1')
        signatures = {
            'new_receiver': (P, P), 'configure_name': (None, P, C.c_char_p),
            'setup_backend_fd': (I, P, I), 'get_fd': (I, P),
            'dispatch': (None, P), 'get_event': (P, P), 'event_unref': (P, P),
            'unref': (P, P), 'event_get_type': (I, P), 'event_get_seat': (P, P),
            'event_get_device': (P, P), 'seat_bind_capabilities': (None, P),
            'device_keyboard_get_keymap': (P, P), 'keymap_get_fd': (I, P),
            'keymap_get_size': (C.c_size_t, P), 'keymap_get_type': (I, P),
            'event_emulating_get_sequence': (U, P),
            'event_scroll_get_dx': (D, P), 'event_scroll_get_dy': (D, P),
            'event_scroll_get_discrete_dx': (I, P), 'event_scroll_get_discrete_dy': (I, P),
            'event_pointer_get_dx': (D, P), 'event_pointer_get_dy': (D, P),
            'event_button_get_button': (U, P), 'event_button_get_is_press': (B, P),
            'event_keyboard_get_key': (U, P), 'event_keyboard_get_key_is_press': (B, P),
        }
        for mod in ('mods_depressed', 'mods_latched', 'mods_locked', 'group'):
            signatures['event_keyboard_get_xkb_' + mod] = (U, P)
        for name, signature in signatures.items():
            bind(self.e, 'ei_' + name, *signature)
        self.x = C.CDLL('libxkbcommon.so.0')
        for name, signature in {
            'context_new': (P, I), 'context_unref': (None, P),
            'keymap_new_from_string': (P, P, C.c_char_p, I, I), 'keymap_unref': (None, P),
            'state_new': (P, P), 'state_unref': (None, P),
            'state_key_get_utf32': (U, P, U),
            'state_update_mask': (I, P, U, U, U, U, U, U),
        }.items():
            bind(self.x, 'xkb_' + name, *signature)
        self.xcontext = self.x.xkb_context_new(0)
        self.states = {}
        self.sequences = {}
        self.scrolls = {}
        self.context = self.e.ei_new_receiver(None)
        self.e.ei_configure_name(self.context, b'DeskDock Wayland host')
        if self.e.ei_setup_backend_fd(self.context, fd) != 0:
            self.close()
            raise RuntimeError('libei could not connect to portal')
        self.fd = self.e.ei_get_fd(self.context)

    def drain(self):
        self.e.ei_dispatch(self.context)
        while event := self.e.ei_get_event(self.context):
            try:
                self.handle(event)
            finally:
                self.e.ei_event_unref(event)

    def handle(self, event):
        e = self.e
        kind = e.ei_event_get_type(event)
        device = e.ei_event_get_device(event)
        if kind == 2:
            self.callback('disconnect', None, None)
        elif kind == 3:
            # Varargs capabilities terminated with a null pointer, per libei API.
            e.ei_seat_bind_capabilities(e.ei_event_get_seat(event), I(1), I(4), I(16), I(32), P())
        elif kind == 5:
            keymap = e.ei_device_keyboard_get_keymap(device)
            if keymap and e.ei_keymap_get_type(keymap) == 1:
                text = os.pread(e.ei_keymap_get_fd(keymap), e.ei_keymap_get_size(keymap), 0)
                compiled = self.x.xkb_keymap_new_from_string(self.xcontext, text, 1, 0)
                if not compiled:
                    raise RuntimeError('Cannot compile compositor keyboard map')
                self.states[device] = self.x.xkb_state_new(compiled)
                self.x.xkb_keymap_unref(compiled)
        elif kind == 6:
            if state := self.states.pop(device, None):
                self.x.xkb_state_unref(state)
            self.sequences.pop(device, None)
        elif kind == 9 and device in self.states:
            mods = [getattr(e, 'ei_event_keyboard_get_xkb_' + name)(event)
                    for name in ('mods_depressed', 'mods_latched', 'mods_locked', 'group')]
            self.x.xkb_state_update_mask(self.states[device], *mods[:3], 0, 0, mods[3])
        elif kind in (600,603):
            scroll = self.scrolls.setdefault(device,{})
            if kind == 603:
                scroll['discrete'] = (e.ei_event_scroll_get_discrete_dx(event)/120, e.ei_event_scroll_get_discrete_dy(event)/120)
            else:
                scroll['delta'] = (e.ei_event_scroll_get_dx(event)/15, e.ei_event_scroll_get_dy(event)/15)
        elif kind == 100:
            if scroll := self.scrolls.pop(device,None):
                self.callback('scroll',scroll.get('discrete',scroll.get('delta')),self.sequences.get(device))
        elif kind == 200:
            self.sequences[device] = e.ei_event_emulating_get_sequence(event)
        elif kind == 201:
            self.sequences.pop(device, None)
            self.scrolls.pop(device, None)
        elif kind == 300:
            self.callback('motion', (e.ei_event_pointer_get_dx(event), e.ei_event_pointer_get_dy(event)), self.sequences.get(device))
        elif kind == 500:
            self.callback('button', (e.ei_event_button_get_button(event), e.ei_event_button_get_is_press(event)), self.sequences.get(device))
        elif kind == 700:
            key = e.ei_event_keyboard_get_key(event)
            down = e.ei_event_keyboard_get_key_is_press(event)
            character = self.x.xkb_state_key_get_utf32(self.states[device], key + 8) if device in self.states else 0
            self.callback('key', (key, character, down), self.sequences.get(device))

    def close(self):
        for state in self.states.values():
            self.x.xkb_state_unref(state)
        self.states.clear()
        if self.context:
            self.e.ei_unref(self.context)
            self.context = None
        if self.xcontext:
            self.x.xkb_context_unref(self.xcontext)
            self.xcontext = None
