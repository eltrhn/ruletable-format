"""Facilitates parsing of a nutshell rule into an abstract, compiler.py-readable format."""
import re
from functools import partial
from itertools import cycle, islice, zip_longest

import bidict
import lark

from nutshell.common.classes import TableRange
from nutshell.common.utils import printv, printq
from nutshell.common.errors import *
from . import _napkins as napkins, _utils as utils, _symmetries as symmetries
from ._classes import SpecialVar, PTCD, VarName
from .lark_assets import NUTSHELL_GRAMMAR, Preprocess, Variable


class Bidict(bidict.bidict):
    on_dup_kv = bidict.OVERWRITE


class Table:
    CARDINALS = utils.generate_cardinals({
      'oneDimensional': ('W', 'E'),
      'vonNeumann': ('N', 'E', 'S', 'W'),
      'hexagonal': ('N', 'E', 'SE', 'S', 'W', 'NW'),
      'Moore': ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'),
      })
    TRLENS = {k: len(v) for k, v in CARDINALS.items()}
    hush = True

    def __init__(self, tbl, start=0, *, dep: ['@NUTSHELL'] = None):
        self._src = tbl
        self._src[:] = [i.split('#')[0].strip() for i in tbl]  # Lark chokes otherwise :/
        self._start = start
        self._n_states = 0
        dep, = dep
        
        if self.hush:
            global printv, printq
            printv = printq = lambda *_, **__: None
        
        self.vars = Bidict()  # {VarName(name) | str(name) :: Variable(value)}
        self.directives = {}
        self.transitions = []
        self._constants = {}
        
        if dep is not None:
            dep.replace(self._src)
            self._constants = dep.constants
            if self._constants:
                self._n_states = max(self._constants.values())
        
        trans = Preprocess(tbl=self)
        parser = lark.Lark(NUTSHELL_GRAMMAR, parser='lalr', start='table', propagate_positions=True)
        printv(['-- loaded grammar'], start='', end='')
        self._data = trans.transform(parser.parse('\n'.join(self._src)))
        printv(['-- parsed'])
    
    def __getitem__(self, item):
        return self._src[item]
    
    @property
    def neighborhood(self):
        return self.CARDINALS[self.directives['neighborhood']]
    
    @property
    def trlen(self):
        return len(self.neighborhood)
    
    @property
    def symmetries(self):
        return self.directives['symmetries']
    
    @property
    def n_states(self):
        return self._n_states
    
    @n_states.setter
    def n_states(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            if value == '?':
                self.vars[VarName('any')] = Variable(self, range(self.n_states))
                self.vars[VarName('live')] = Variable(self, range(1, self.n_states))
        else:
            if value > self.n_states:
                self._n_states = value
                self.vars[VarName('any')] = Variable(self, range(value))
                self.vars[VarName('live')] = Variable(self, range(1, value))
