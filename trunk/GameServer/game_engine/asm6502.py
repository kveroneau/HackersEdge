import mmap, re, logging
from exceptions import CompileError

log = logging.getLogger('HackerASM')

class AssembleError(CompileError):
    pass

OP_CODES = {
    # Name, Imm,  ZP,   ZPX,  ZPY,  ABS, ABSX, ABSY,  IND, INDX, INDY, SNGL, BRA,  ZPI
    'ADC': [0x69, 0x65, 0x75, None, 0x6d, 0x7d, 0x79, None, 0x61, 0x71, None, None, 0x72],
    'AND': [0x29, 0x25, 0x35, None, 0x2d, 0x3d, 0x39, None, 0x21, 0x31, None, None, 0x32],
    'ASL': [None, 0x06, 0x16, None, 0x0e, 0x1e, None, None, None, None, 0x0a, None, None],
    'BIT': [0x89, 0x24, 0x34, None, 0x2c, 0x3c, None, None, None, None, None, None, None],
    'BPL': [None, None, None, None, None, None, None, None, None, None, None, 0x10, None],
    'BMI': [None, None, None, None, None, None, None, None, None, None, None, 0x30, None],
    'BVC': [None, None, None, None, None, None, None, None, None, None, None, 0x50, None],
    'BVS': [None, None, None, None, None, None, None, None, None, None, None, 0x70, None],
    'BCC': [None, None, None, None, None, None, None, None, None, None, None, 0x90, None],
    'BCS': [None, None, None, None, None, None, None, None, None, None, None, 0xb0, None],
    'BNE': [None, None, None, None, None, None, None, None, None, None, None, 0xd0, None],
    'BEQ': [None, None, None, None, None, None, None, None, None, None, None, 0xf0, None],
    'BRK': [0x00, None, None, None, None, None, None, None, None, None, 0x00, None, None],
    'CMP': [0xc9, 0xc5, 0xd5, None, 0xcd, 0xdd, 0xd9, None, 0xc1, 0xd1, None, None, 0xd2],
    'CPX': [0xe0, 0xe4, None, None, 0xec, None, None, None, None, None, None, None, None],
    'CPY': [0xc0, 0xc4, None, None, 0xcc, None, None, None, None, None, None, None, None],
    'DEC': [None, 0xc6, 0xd6, None, 0xce, 0xde, None, None, None, None, 0x3a, None, None],
    'EOR': [0x49, 0x45, 0x55, None, 0x4d, 0x5d, 0x59, None, 0x41, 0x51, None, None, 0x52],
    'CLC': [None, None, None, None, None, None, None, None, None, None, 0x18, None, None],
    'SEC': [None, None, None, None, None, None, None, None, None, None, 0x38, None, None],
    'CLI': [None, None, None, None, None, None, None, None, None, None, 0x58, None, None],
    'SEI': [None, None, None, None, None, None, None, None, None, None, 0x78, None, None],
    'CLV': [None, None, None, None, None, None, None, None, None, None, 0xb8, None, None],
    'CLD': [None, None, None, None, None, None, None, None, None, None, 0xd8, None, None],
    'SED': [None, None, None, None, None, None, None, None, None, None, 0xf8, None, None],
    'INC': [None, 0xe6, 0xf6, None, 0xee, 0xfe, None, None, None, None, 0x1a, None, None],
    'JMP': [None, None, None, None, 0x4c, 0x7c, None, 0x6c, None, None, None, None, None],
    'JSR': [None, None, None, None, 0x20, None, None, 0x3f, None, None, None, None, None],
    'LDA': [0xa9, 0xa5, 0xb5, None, 0xad, 0xbd, 0xb9, None, 0xa1, 0xb1, None, None, 0xb2],
    'LDX': [0xa2, 0xa6, None, 0xb6, 0xae, None, 0xbe, None, None, None, None, None, None],
    'LDY': [0xa0, 0xa4, 0xb4, None, 0xac, 0xbc, None, None, None, None, None, None, None],
    'LSR': [None, 0x46, 0x56, None, 0x4e, 0x5e, None, None, None, None, 0x4a, None, None],
    'NOP': [None, None, None, None, None, None, None, None, None, None, 0xea, None, None],
    'ORA': [0x09, 0x05, 0x15, None, 0x0d, 0x1d, 0x19, None, 0x01, 0x11, None, None, 0x12],
    'TAX': [None, None, None, None, None, None, None, None, None, None, 0xaa, None, None],
    'TXA': [None, None, None, None, None, None, None, None, None, None, 0x8a, None, None],
    'DEX': [None, None, None, None, None, None, None, None, None, None, 0xca, None, None],
    'INX': [None, None, None, None, None, None, None, None, None, None, 0xe8, None, None],
    'TAY': [None, None, None, None, None, None, None, None, None, None, 0xa8, None, None],
    'TYA': [None, None, None, None, None, None, None, None, None, None, 0x98, None, None],
    'DEY': [None, None, None, None, None, None, None, None, None, None, 0x88, None, None],
    'INY': [None, None, None, None, None, None, None, None, None, None, 0xc8, None, None],
    'ROR': [None, 0x66, 0x76, None, 0x6e, 0x7e, None, None, None, None, 0x6a, None, None],
    'ROL': [None, 0x26, 0x36, None, 0x2e, 0x3e, None, None, None, None, 0x2a, None, None],
    'RTI': [None, None, None, None, None, None, None, None, None, None, 0x40, None, None],
    'RTS': [None, None, None, None, None, None, None, None, None, None, 0x60, None, None],
    'SBC': [0xe9, 0xe5, 0xf5, None, 0xed, 0xfd, 0xf9, None, 0xe1, 0xf1, None, None, 0xf2],
    'STA': [None, 0x85, 0x95, None, 0x8d, 0x9d, 0x99, None, 0x81, 0x91, None, None, 0x92],
    'TXS': [None, None, None, None, None, None, None, None, None, None, 0x9a, None, None],
    'TSX': [None, None, None, None, None, None, None, None, None, None, 0xba, None, None],
    'PHA': [None, None, None, None, None, None, None, None, None, None, 0x48, None, None],
    'PLA': [None, None, None, None, None, None, None, None, None, None, 0x68, None, None],
    'PHP': [None, None, None, None, None, None, None, None, None, None, 0x08, None, None],
    'PLP': [None, None, None, None, None, None, None, None, None, None, 0x28, None, None],
    'STX': [None, 0x86, None, 0x96, 0x8e, None, None, None, None, None, None, None, None],
    'STY': [None, 0x84, 0x94, None, 0x8c, None, None, None, None, None, None, None, None],
    'BRA': [None, None, None, None, None, None, None, None, None, None, None, 0x80, None],
    'PHX': [None, None, None, None, None, None, None, None, None, None, 0xda, None, None],
    'PLX': [None, None, None, None, None, None, None, None, None, None, 0xfa, None, None],
    'PHY': [None, None, None, None, None, None, None, None, None, None, 0x5a, None, None],
    'PLY': [None, None, None, None, None, None, None, None, None, None, 0x7a, None, None],
    'STZ': [None, 0x64, 0x74, None, 0x9c, 0x9e, None, None, None, None, None, None, None],
    'TRB': [None, 0x14, None, None, 0x1c, None, None, None, None, None, None, None, None],
    'TSB': [None, 0x04, None, None, 0x0c, None, None, None, None, None, None, None, None],
}

PATTERN_MAP = {
    'imm': 0,
    'immp': 0,
    'immm': 0,
    'immd': 0,
    'immb': 0,
    'immdp': 0,
    'immdm': 0,
    'immc': 0,
    'immcp': 0,
    'immcm': 0,
    'zp': 1,
    'zpp': 1,
    'zpm': 1,
    'zpd': 1,
    'zpx': 2,
    'zpy': 3,
    'abs': 4,
    'absx': 5,
    'absy': 6,
    'ind': 7,
    'indx': 8,
    'indy': 9,
    'bra': 11,
    'locbra': 11,
    'zpi': 12,
}

patterns = {
    'comments': re.compile('^(.*?);.*'),
    'label': re.compile('^(\w+):(.*)$'),
    'abslabel': re.compile('^(\@\w+):(.*)$'),
    'loclabel': re.compile('^\.(\w+):(.*)$'),
    'const': re.compile('^def (\w+) (\$[0-9a-f]{1,4})$'),
    'api': re.compile('^def \%(\w+) \((\$[0-9a-f]{1,4})\)$'),
    'imm': re.compile('^#\$([0-9A-F]{1,2})$'),
    'immp': re.compile('^#\$([0-9A-F]{1,2})\+([0-9]{1,2})$'),
    'immm': re.compile('^#\$([0-9A-F]{1,2})\-([0-9]{1,2})$'),
    'immd': re.compile('^#([0-9]{1,3})$'),
    'immb': re.compile('^#%([0-1]{4}\.[0-1]{4})$'),
    'immdp': re.compile('^#([0-9]{1,3})\+([0-9]{1,2})$'),
    'immdm': re.compile('^#([0-9]{1,3})\-([0-9]{1,2})$'),
    'immc': re.compile('^#"(.)"$'),
    'immcp': re.compile('^#"(.)"\+([0-9]{1,2})$'),
    'immcm': re.compile('^#"(.)"\-([0-9]{1,2})$'),
    'ind': re.compile('^\(\$([0-9A-F]{3,4})\)$'),
    'indx': re.compile('^\(\$([0-9A-F]{1,2}),X\)$'),
    'indy': re.compile('^\(\$([0-9A-F]{1,2})\),Y$'),
    'zp': re.compile('^\$([0-9A-Fa-f]{1,2})$'),
    'zpp': re.compile('^\$([0-9A-Fa-f]{1,2})\+([0-9]{1,2})$'),
    'zpm': re.compile('^\$([0-9A-Fa-f]{1,2})\-([0-9]{1,2})$'),
    'zpd': re.compile('^([0-9]{1,3})$'),
    'abs': re.compile('^\$([0-9A-F]{3,4})$'),
    'absx': re.compile('^\$([0-9A-F]{3,4}),X$'),
    'absy': re.compile('^\$([0-9A-F]{3,4}),Y$'),
    'zpx': re.compile('^\$([0-9A-F]{1,2}),X$'),
    'zpy': re.compile('^\$([0-9A-F]{1,2}),Y$'),
    'bra': re.compile('^(\w+)$'),
    'locbra': re.compile('^\.(\w+)$'),
    'zpi': re.compile('^\(\$([0-9A-F]{1,2})\)$'),
}

class Assembler(object):
    version = 'HackerASM v1.2.1 $Rev: 261 $'
    def __init__(self, lines):
        self.memsize = 0x2
        self.mem = mmap.mmap(-1, self.memsize << 8)
        self.dmem = mmap.mmap(-1, 512)
        self.lines = lines
        self.labels = {}
        self.hi_var = {}
        self.lo_var = {}
        self.vars = {'%ds':'($f0)'}
        self.branches = {}
        self.last_lbl = ''
        self.dseg = False
        self.outfile = None
        self.result = ''
        self.bintype = 'HEBIN'
        self.org = 0x0
    def resize_mem(self, newsize):
        tmp = mmap.mmap(-1, self.memsize << 8)
        ptr = self.mem.tell()
        self.mem.seek(0)
        tmp.write(self.mem.read(self.memsize << 8))
        self.mem.close()
        self.mem = mmap.mmap(-1, newsize << 8)
        tmp.seek(0)
        self.mem.write(tmp.read(self.memsize << 8))
        tmp.close()
        self.mem.seek(ptr)
        self.memsize = newsize
    def format_hex(self, dec, sz=2):
        fmt = '0000'+hex(dec)[2:]
        return '$%s' % fmt[-sz:].upper()
    def get_label(self, label, offset=1):
        if self.dseg and label in self.labels.keys():
            return self.format_hex(self.labels[label][0], 4)
        if label in self.labels.keys():
            self.labels[label][1].append(self.mem.tell()+offset)
        else:
            self.labels[label] = [1024,[self.mem.tell()+offset]]
        sz = 4 if label.startswith('@') else 2
        return self.format_hex(self.labels[label][0], sz)
    def set_label(self, label, value):
        label = label.upper()
        if label in self.labels.keys():
            self.labels[label][0] = value+self.org
            for ptr in self.labels[label][1]:
                if value < 256:
                    self.mem[ptr] = chr(value & 0xff)
                if label.startswith('@'):
                    v = value+self.org
                    self.mem[ptr] = chr(v & 0xff)
                    self.mem[ptr+1] = chr((v >> 8) & 0xff)
        else:
            self.labels[label] = [value, []]
        value = value+self.org
        if label in self.hi_var.keys():
            self.hi_var[label][0] = value & 0xff
            for ptr in self.hi_var[label][1]:
                self.mem[ptr] = chr(value & 0xff)
        if label in self.lo_var.keys():
            self.lo_var[label][0] = (value >> 8) & 0xff
            for ptr in self.lo_var[label][1]:
                self.mem[ptr] = chr((value >> 8) & 0xff)
                #self.labels[label][1].append(ptr)
    def get_branch(self, label):
        if label in self.branches.keys():
            self.branches[label][1].append(self.mem.tell())
        else:
            self.branches[label] = [-1,[self.mem.tell()]]
        value = self.branches[label][0]
        if value < self.mem.tell():
            return (0xff - (self.mem.tell() - value)) & 0xff
        else:
            return (value - self.mem.tell() - 1) & 0xff
    def set_branch(self, label, value):
        label = label.upper()
        if label in self.branches.keys():
            self.branches[label][0] = value
            for ptr in self.branches[label][1]:
                if value < ptr:
                    self.mem[ptr] = chr((0xff - (ptr - value)) & 0xff)
                else:
                    self.mem[ptr] = chr((value - ptr - 1) & 0xff)
        else:
            self.branches[label] = [value, []]
    def dcb(self, params):
        for value in params.split(','):
            v = patterns['zp'].match(value.strip())
            if not v:
                if len(value.strip()) == 1:
                    if self.dseg:
                        self.dmem.write(value.strip())
                    else:
                        self.mem.write(value.strip())
                    continue
                else:
                    raise AssembleError('Bad DCB value: %s' % value)
            if self.dseg:
                self.dmem.write(chr(int(v.group(1), 16)))
            else:
                self.mem.write(chr(int(v.group(1), 16)))
    def dcs(self, params):
        if self.dseg:
            self.dmem.write(params.replace('\\n', '\n').replace('\\0','\0'))
        else:
            self.mem.write(params.replace('\\n', '\n').replace('\\0','\0'))
    def dcw(self, params):
        for value in params.split(','):
            v = patterns['abs'].match(value.strip())
            if not v:
                if value.strip() not in self.labels.keys():
                    raise AssembleError('Bad DCW value: %s' % value)
                v = int(self.get_label(value.strip(),0)[1:], 16)
            else:
                try:
                    v = int(v.group(1), 16)
                except:
                    raise AssembleError('Bad DCW value: %s' % value)
            if self.dseg:
                self.dmem.write(chr(v & 0xff))
                self.dmem.write(chr((v >> 8) & 0xff))
            else:
                self.mem.write(chr(v & 0xff))
                self.mem.write(chr((v >> 8) & 0xff))
    def check_implicit(self, param, opcode):
        if opcode is None:
            return False
        self.mem.write(chr(opcode))
        if opcode == 0x00:
            self.mem.write(chr(0))
        return True
    def assembleLine(self, line):
        if ' ' in line:
            op, param = line.split(' ',1)
        elif line in OP_CODES.keys():
            if not self.check_implicit('', OP_CODES[line][10]):
                raise AssembleError('Bad implicit: %s' % line)
            return
        else:
            raise AssembleError('Syntax error: %s' % line)
        if op in ('LDA', 'LDX', 'LDY',):
            if param.startswith('#>@'):
                if param[2:] in self.hi_var.keys():
                    self.hi_var[param[2:]][1].append(self.mem.tell()+1)
                    param='#%s' % self.format_hex(self.hi_var[param[2:]][0], 2)
            elif param.startswith('#<@'):
                if param[2:] in self.lo_var.keys():
                    self.lo_var[param[2:]][1].append(self.mem.tell()+1)
                    param='#%s' % self.format_hex(self.lo_var[param[2:]][0], 2)
        if not op.startswith('B') and op not in ('BIT', 'BRK', 'DCW',):
            for label in self.labels.keys():
                if label in param:
                    param=param.replace(label, self.get_label(label))
        if op == 'DCB':
            self.dcb(self.real_line.split(' ',1)[1])
        elif op == 'DCS':
            self.dcs(self.real_line.split(' ',1)[1])
        elif op == 'DCW':
            self.dcw(param)
        elif op in OP_CODES.keys():
            found_checker = False
            for checker, pattern in patterns.items():
                value = pattern.match(param)
                if value:
                    found_checker = True
                    opcode = OP_CODES[op][PATTERN_MAP[checker]]
                    if not opcode:
                        raise AssembleError('Incorrect parameters used: %s' % self.real_line)
                    self.mem.write(chr(opcode))
                    if checker == 'bra':
                        v = self.get_branch(value.group(1))
                    elif checker == 'locbra':
                        v = self.get_branch('%s.%s' % (self.last_lbl, value.group(1)))
                    elif checker == 'immc':
                        v = ord(value.group(1))
                    elif checker == 'immcp':
                        v = ord(value.group(1))+int(value.group(2))
                    elif checker == 'immcm':
                        v = ord(value.group(1))-int(value.group(2))
                    elif checker == 'immdp':
                        v = int(value.group(1), 10)+int(value.group(2))
                    elif checker == 'immdm':
                        v = int(value.group(1), 10)-int(value.group(2))
                    elif checker == 'immb':
                        v = int(value.group(1).replace('.',''), 2)
                    elif checker in ('immp', 'zpp'):
                        v = int(value.group(1), 16)+int(value.group(2))
                    elif checker in ('immm', 'zpm'):
                        v = int(value.group(1), 16)-int(value.group(2))
                    elif checker not in ('immd', 'zpd',):
                        v = int(value.group(1), 16)
                    else:
                        v = int(value.group(1), 10)
                    if checker in ('ind', 'abs', 'absx', 'absy',):
                        self.mem.write(chr(v & 0xff))
                        self.mem.write(chr((v >> 8) & 0xff))
                    else:
                        self.mem.write(chr(v & 0xff))
            if not found_checker:
                #raise AssembleError('Param: %s' % param)
                raise AssembleError('Syntax error: %s' % line)
        else:
            raise AssembleError('Invalid Opcode: %s' % op)
    def find_labels(self):
        last_lbl = ''
        for line in self.lines:
            line = line.strip()
            command = patterns['label'].match(line)
            if command:
                last_lbl = label = command.group(1)
                self.set_label(label, 128)
                continue
            command = patterns['abslabel'].match(line)
            if command:
                label = command.group(1)
                self.set_label(label, 1024)
                self.hi_var[label.upper()] = [1024, []]
                self.lo_var[label.upper()] = [1024, []]
                continue
            command = patterns['loclabel'].match(line)
            if command:
                label = '%s.%s' % (last_lbl, command.group(1))
                self.set_label(label, 128)
    def assemble(self):
        self.find_labels()
        for line in self.lines:
            self.real_line = line
            line = line.strip()
            if line == '.DATA':
                self.set_label('@DATA', self.mem.tell())
                self.dseg = True
                continue
            elif line.startswith('.INITDATA '):
                self.vars['%ds'] = '(%s)' % line[10:]
                dsp = int(line[11:],16)
                self.set_label('@DATA', 1024)
                self.hi_var['@DATA'] = [1024, []]
                self.lo_var['@DATA'] = [1024, []]
                self.assembleLine('LDA #>@DATA')
                self.assembleLine('STA $%s' % hex(dsp)[2:])
                self.assembleLine('LDA #<@DATA')
                self.assembleLine('STA $%s' % hex(dsp+1)[2:])
                continue
            elif line == '.PAGE':
                if self.bintype == 'HEBIN':
                    raise AssembleError('Executable binary images do not support pages.')
                self.resize_mem(self.memsize+1)
                page = self.mem.tell() >> 8 
                self.mem.seek(page+1 << 8)
                continue
            elif line.startswith('.OUT '):
                self.outfile = line[5:]
                continue
            elif line.startswith('.TYP '):
                if self.bintype not in ('HEBIN', 'ORG'):
                    raise AssembleError('Binary type %s already selected!' % self.bintype)
                typ = line[5:]
                if typ == 'RAW':
                    self.bintype = 'RAW'
                else:
                    raise AssembleError('Unknown BINTYPE provided: %s' % typ)
                continue
            elif line.startswith('.ORG '):
                if self.org > 0:
                    raise AssembleError('Address originator already set.')
                if self.bintype != 'HEBIN':
                    raise AssembleError('Cannot mix ORG and TYP!')
                self.bintype = 'ORG'
                self.org = int(line[6:], 16)
                continue
            command = patterns['comments'].match(line)
            if command:
                line = command.group(1).strip()
            command = patterns['label'].match(line)
            if command:
                label = command.group(1)
                self.last_lbl = label
                line = command.group(2).strip()
                if self.dseg:
                    self.set_label(label, self.dmem.tell())
                else:
                    self.set_label(label, self.mem.tell())
                self.set_branch(label, self.mem.tell())
            command = patterns['loclabel'].match(line)
            if command:
                label = '%s.%s' % (self.last_lbl, command.group(1))
                line = command.group(2).strip()
                if self.dseg:
                    self.set_label(label, self.dmem.tell())
                else:
                    self.set_label(label, self.mem.tell())
                self.set_branch(label, self.mem.tell())
            command = patterns['abslabel'].match(line)
            if command:
                if self.dseg:
                    raise AssembleError('Cannot use absolute labels in DATA segment.')
                label = command.group(1)
                line = command.group(2).strip()
                self.set_label(label, self.mem.tell())
                self.set_branch(label, self.mem.tell())
            command = patterns['const'].match(line.lower())
            if command:
                var = command.group(1)
                value = command.group(2)
                line = ''
                self.vars[var] = value
            command = patterns['api'].match(line.lower())
            if command:
                var = '%%%s' % command.group(1)
                value = '(%s)' % command.group(2)
                line = ''
                self.vars[var] = value
            if line != '':
                for var in self.vars.items():
                    if var[0] in line:
                        line=line.replace(*var)
                self.assembleLine(line.upper())
        for lbl,bra in self.branches.items():
            if bra[0] == -1:
                raise AssembleError('Missing label: %s' % lbl)
    def savebin(self, binfile):
        size = self.mem.tell()
        dsize = self.dmem.tell()
        if self.bintype == 'HEBIN':
            if size > 255:
                raise AssembleError('CODE segment exceeds 255 bytes.')
            if dsize > 255:
                raise AssembleError('DATA segment exceeds 255 bytes.')
            self.result = 'Code segment: %s/255' % size
            if dsize > 0:
                self.result+='\r\nData segment: %s/255' % dsize
        else:
            self.result = 'Generating binary type: %s\r\n' % self.bintype
            self.result+='Binary size: %s' % size
            if dsize > 0:
                self.result+='\r\nData size: %s' % dsize
        self.mem.seek(0)
        self.dmem.seek(0)
        with open(binfile, 'wb') as f:
            if self.bintype == 'HEBIN':
                f.write(chr(0xff)+chr(0))
                reloc = 0
                rtbl = ''
                for label, value in self.labels.items():
                    if label.startswith('@'):
                        if len(value[1]) > 0:
                            for ptr in value[1]:
                                reloc+=1
                                rtbl+=chr(ptr)
                f.write(chr(reloc)+rtbl)
                f.write(chr(dsize)+self.dmem.read(dsize))
            elif self.bintype == 'ORG':
                f.write(chr(0xfe)+chr(self.org >> 8)+chr(0))
                f.write(chr((0xfe+(self.org >> 8)+0)%256))
            f.write(self.mem.read(size))
            if self.bintype == 'RAW' and dsize > 0:
                f.write(self.dmem.read(dsize))
    def get_header(self):
        if self.bintype == 'HEBIN':
            return '' # TODO: Move over HEBIN binary header code
        elif self.bintype == 'ORG':
            return chr(0xfe)+chr(self.org >> 8)+chr(0)+chr((0xfe+(self.org >> 8)+0)%256)
        return ''
    def get_cseg(self):
        self.result = 'Generating binary type: %s\r\n' % self.bintype
        size = self.mem.tell()
        self.mem.seek(0)
        if self.bintype == 'RAW' and self.dseg:
            dsize = self.dmem.tell()
            self.dmem.seek(0)
            self.result+='Binary size: %s' % str(size+dsize)
            return self.mem.read(size)+self.dmem.read(dsize)
        self.result+='Binary size: %s' % size
        return self.mem.read(size)
    def get_dseg(self):
        size = self.dmem.tell()
        self.dmem.seek(0)
        return self.dmem.read(size)
