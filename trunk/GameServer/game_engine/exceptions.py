
class EngineError(Exception):
    pass

class EngineState(Exception):
    pass

class VMError(EngineError):
    pass

class BankError(EngineError):
    pass

class ShellError(EngineError):
    pass

class SwitchHost(EngineState):
    pass

class CompileError(VMError):
    pass

class VMNoData(VMError):
    pass

class VMFlush(VMError):
    pass

class VMNetData(VMError):
    pass

class VMHalt(EngineState):
    pass

class VMReset(EngineState):
    pass

class VMTermBit(EngineState):
    pass
