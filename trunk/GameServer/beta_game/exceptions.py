
class ShellError(Exception):
    pass

class SwitchShell(Exception):
    pass

class ConfigurationError(Exception):
    pass

class BankError(Exception):
    pass

class CompileError(Exception):
    pass

class VMError(Exception):
    pass

class ExecuteBin(Exception):
    pass

class CloseSession(Exception):
    pass

class VMNoData(Exception):
    pass

class VMFlush(Exception):
    pass

class SessionCtrl(Exception):
    pass

class VMNetData(Exception):
    pass

class SwitchState(Exception):
    pass

class SwitchHost(Exception):
    pass
