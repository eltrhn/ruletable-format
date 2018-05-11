import re
import random
from collections import defaultdict
from itertools import chain, filterfalse, groupby, takewhile
from math import ceil

import bidict

#from ..common.classes.errors import TabelReferenceError, TabelValueError


SYMBOL_MAP = bidict.frozenbidict({
    0: '.',
  **{num: chr(64+num) for num in range(1, 25)},
  **{num: chr(110 + ceil(num/24)) + chr(64 + (num % 24 or 24)) for num in range(25, 256)}
  })

TWO_BYTE_CHARS = ''.join(filter(str.isprintable, map(chr, range(0x100, 0x800))))


def lazylen(iterable):
    return sum(1 for _ in iterable)


class Icon:
    HEIGHT = None
    _FILL = None
    _rRUNS = re.compile(r'(\d*)([$.A-Z]|[p-y][A-O])')
    
    def __init__(self, rle):
        if self.HEIGHT not in (7, 15, 31):
            raise ValueError(f"Need to declare valid height (not '{self.HEIGHT!r}')")
        self._FILL = ['..' * self.HEIGHT]
        self._rle = rle
        self._split =''.join(
          (val * 2 if len(val.encode()) < 2 else val) * int(run_length or 1)
          for run_length, val in
            self._rRUNS.findall(self._rle)
          ).split('$$')
        self.ascii = self._pad()
    
    def __iter__(self):
        return iter(self.ascii)

    @classmethod
    def set_height(cls, dims):
        max_dim = max(map(max, zip(*dims)))
        cls.HEIGHT = min((7, 15, 31), key=lambda x: abs(max_dim-x))
    
    @classmethod
    def solid_color(cls, color):
        if len(color.encode()) < 2:
            color *= 2
        return [color * cls.HEIGHT] * cls.HEIGHT
    
    def _pad(self):
        # Horizontal padding
        earliest = min(lazylen(takewhile('.'.__eq__, line)) for line in self._split)
        max_len = max(map(len, self._split))
        # Vertical padding
        pre = len(self._split) // 2
        post = len(self._split) - pre
        return self._FILL * pre + [f"{f'{line[earliest:]:.<{max_len}}':.^{2*self.HEIGHT}}" for line in self._split] + self._FILL * post


class IconArray:
    _rDIMS = re.compile(r'\s*x\s*=\s*(\d+),\s*y\s*=\s*(\d+)')
    _rCOLOR = re.compile(r'\s*(\d+|[.A-Z]|[p-y][A-O])\s+([0-9A-F]{6}|[0-9A-F]{3}).*')
    
    def __init__(self, seg, start=0, *, dep: '@COLORS'):
        self._src = seg
        self._start = start
        self._parsed_color_segment = dep
        
        self.colormap, _start_state_def = self._parse_colors(start)
        self._states = self._sep_states(_start_state_def)
        
        # this mess just constructs a "sequence" of (x, y) coords to pass to set_height(), grabbed from the RLEs in self._states.values()
        Icon.set_height(map(lambda x: map(int, chain.from_iterable(self._rDIMS.findall(x))), filter(self._rDIMS.match, chain.from_iterable(self._states.values()))))
        
        self.icons = {state: list(Icon(''.join(rle))) for state, (_dims, *rle) in self._states.items()}
        self._fill_missing_states()
    
    def __iter__(self):
        yield 'XPM'
        # /* width height num_colors chars_per_pixel */
        yield f'"{Icon.HEIGHT} {len(self.icons)*Icon.HEIGHT} {len(self.colormap)} 2"'
        # /* colors */
        yield from (f'"{(symbol * 2 if len(symbol.encode()) < 2 else symbol)} c #{color}"' for symbol, color in self.colormap.items())
        # /* icons */
        yield from (f'"{line}"' for icon in (self.icons[key] for key in sorted(self.icons)) for line in icon)
    
    @staticmethod
    def _make_name():
        return random.choice(TWO_BYTE_CHARS)
    
    def _parse_colors(self, start=0):
        lno, colormap = start, {}
        for lno, line in enumerate(self._src):
            match = self._rCOLOR.match(line)
            if match is None:
                if line:
                    break
                continue
            state, color = match.groups()
            if len(color) < 6:
                color *= 2
            colormap[SYMBOL_MAP[int(state)] if state.isdigit() else state * 2 if len(state.encode()) < 2 else state] = color.upper()
        return colormap, lno

    def _sep_states(self, start) -> dict:
        states = defaultdict(list)
        for lno, line in enumerate(map(str.strip, self._src[start:]), start):
            if not line:
                continue
            if line.startswith('#'):
                cur_state = int(''.join(filter(str.isdigit, line)))
                if not 0 < cur_state < 256:
                    raise TabelValueError(lno, f'Icon given for invalid state {cur_state}')
                continue
            states[cur_state].append(line)
        return states
    
    def _fill_missing_states(self):
        # Account for that some/all cellstates may be expressed as non-numeric symbols rather than their state's number
        _colormap_inv = {v: k for k, v in self.colormap.items()}
        max_state = max(SYMBOL_MAP.inv.get(state, state) for state in self.icons)
        for state in filterfalse(self.icons.__contains__, range(1, max_state)):
            try:
                color = self._parsed_color_segment[state]
            except KeyError:
                raise TabelReferenceError(self._start, f'No @ICONS-defined icon (and, subsequently, no substitute @COLORS-defined fill color) found for state {state}')
            symbol = _colormap_inv.get(color, self._make_name())
            self.colormap[symbol] = color
            self.icons[state] = Icon.solid_color(symbol)