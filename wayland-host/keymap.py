"""Shared physical key mappings, with no desktop imports."""
# Linux evdev keys to Android KeyEvent values, including US physical positions.
KEYS = {99:120, 1:111, 14:67, 15:61, 28:66, 29:113, 42:59, 54:60, 56:57,
        57:62, 58:115, 97:114, 100:58, 102:122, 103:19, 104:92,
        105:21, 106:22, 107:123, 108:20, 109:93, 110:124, 111:112,
        125:117, 126:118, 158:4, 12:69, 13:70, 26:71, 27:72,
        39:74, 40:75, 41:68, 43:73, 51:55, 52:56, 53:76}
for row, letters in ((16,'qwertyuiop'), (30,'asdfghjkl'), (44,'zxcvbnm')):
    KEYS.update({row+i: 29+ord(letter)-ord('a') for i, letter in enumerate(letters)})
KEYS.update({2+i:8+i for i in range(9)})
KEYS[11] = 7
KEYS.update({59+i:131+i for i in range(10)})
KEYS.update({87:141,88:142})

