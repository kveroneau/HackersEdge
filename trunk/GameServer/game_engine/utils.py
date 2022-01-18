from exceptions import BankError
from settings import DEBUG, RANKING_SERVER
from email.mime.text import MIMEText
import smtplib, re, urllib2, json

valid_data = re.compile("^[a-z0-9\_*]+$")
ipv4 = re.compile(r'^(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}$')
valid_ascii = re.compile("^[ -~]+$")

class Shell(object):
    help_header = 'Available commands'
    def parse_cmd(self, prefix, symb=False, *cmdline):
        cmd = cmdline[0]
        if symb:
            cmd = cmd[1:]
        handler = getattr(self, '%s_%s' % (prefix, cmd), None)
        admin = getattr(handler, 'admin', False)
        staff = getattr(handler, 'staff', False)
        designer = getattr(handler, 'designer', False)
        checker = getattr(handler, 'checker', None)
        args = getattr(handler, '__args__', False)
        if admin and not self.admin:
            handler = None
        if staff and not self.staff:
            handler = None
        if designer and not self.designer:
            handler = None
        if handler:
            if args and len(cmdline[1:]) != args:
                self.transmit(' ** Incorrect amount of arguments.')
                self.transmit(' ** Usage: %s %s' % (cmdline[0], getattr(handler, '__usage__', '...')))
                return True
            if checker is not None:
                for chk in checker.split(','):
                    getattr(self, 'check_%s' % chk)(cmdline[1:])
            handler(cmdline[1:])
            return True
        else:
            return False
    def show_help(self, prefix, symb=''):
        prefix = '%s_' % prefix
        plen = len(prefix)
        self.transmit(self.help_header)
        self.transmit('='*len(self.help_header))
        for cmd in dir(self.__class__):
            if cmd[:plen] == prefix:
                func = getattr(self, cmd)
                doc = getattr(self, cmd).__doc__
                if doc is None:
                    continue
                admin = getattr(func, 'admin', False)
                staff = getattr(func, 'staff', False)
                designer = getattr(func, 'designer', False)
                if admin and not self.admin:
                    continue
                if staff and not self.staff:
                    continue
                if designer and not self.designer:
                    continue
                try:
                    usage = '%s %s' % (cmd[plen:], getattr(self, cmd).__usage__)
                except:
                    usage = cmd[plen:]
                usage = symb+usage
                self.transmit(' %25s   %s' % (usage, doc))
    def columnize(self, list, displaywidth=80):
        """Display a list of strings as a compact set of columns.

        Each column is only as wide as necessary.
        Columns are separated by two spaces (one was not legible enough).
        """
        if not list:
            self.transmit("<empty>")
            return
        nonstrings = [i for i in range(len(list))
                        if not isinstance(list[i], str)]
        if nonstrings:
            raise TypeError, ("list[i] not a string for i in %s" %
                              ", ".join(map(str, nonstrings)))
        size = len(list)
        if size == 1:
            self.transmit('%s'%str(list[0]))
            return
        # Try every row count from 1 upwards
        for nrows in range(1, len(list)):
            ncols = (size+nrows-1) // nrows
            colwidths = []
            totwidth = -2
            for col in range(ncols):
                colwidth = 0
                for row in range(nrows):
                    i = row + nrows*col
                    if i >= size:
                        break
                    x = list[i]
                    colwidth = max(colwidth, len(x))
                colwidths.append(colwidth)
                totwidth += colwidth + 2
                if totwidth > displaywidth:
                    break
            if totwidth <= displaywidth:
                break
        else:
            nrows = len(list)
            ncols = 1
            colwidths = [0]
        for row in range(nrows):
            texts = []
            for col in range(ncols):
                i = row + nrows*col
                if i >= size:
                    x = ""
                else:
                    x = list[i]
                texts.append(x)
            while texts and not texts[-1]:
                del texts[-1]
            for col in range(len(texts)):
                texts[col] = texts[col].ljust(colwidths[col])
            self.transmit("%s"%str("  ".join(texts)))
    def tab_completion(self, ibuf):
        return []

def hecmd(usage, args=False, admin=False, staff=False, designer=False, checker=None):
    def wrap(func):
        def wrapped_f(*args):
            return func(*args)
        f = wrapped_f
        f.__doc__ = func.__doc__
        f.__usage__ = usage
        f.__args__ = args
        f.admin = admin
        f.staff = staff
        f.designer = designer
        f.checker = checker
        return f
    return wrap

def uptime():
    from datetime import timedelta
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        return str(timedelta(seconds=uptime_seconds))

def get_balance(server, username):
    try:
        # TODO: Replace with VM memory access commands.
        pass
    except:
        raise
        raise BankError('Account error, unable to process transaction.')

def transfer_credits(frm, to, amount):
    from_bal = get_balance(*frm)
    if amount > from_bal:
        raise
        raise BankError('Account #%s has insuffient funds.' % frm[1])
    to_bal = get_balance(*to)
    from_bal-=amount
    to_bal+=amount
    #open_file('%s:%s' % frm, 'w').write(str(from_bal))
    #open_file('%s:%s' % to, 'w').write(str(to_bal))

def get_xp(username):
    return get_balance(RANKING_SERVER, username)

def add_xp(username, points):
    xp = get_balance(RANKING_SERVER, username)
    xp+=points
    #open_file('%s:%s' % (RANKING_SERVER, username), 'w').write(str(xp))

def setup_rank(username):
    pass
    #open_file('%s:%s' % (RANKING_SERVER, username), 'w').write(str(0))

def setup_bank(server, username):
    pass
    #open_file('%s:%s' % (server, username), 'w').write(str(1000))

def send_traceback(exc_info):
    import traceback
    if DEBUG:
        print '\n'.join(traceback.format_tb(exc_info()[2]))
        return
    msg = MIMEText('\n'.join(traceback.format_tb(exc_info[2])))
    msg['Subject'] = '%s: %s' % (exc_info[0], exc_info[1])
    msg['From'] = 'devnull@hackers-edge.com'
    msg['To'] = 'chronoboy'
    s = smtplib.SMTP('localhost')
    s.sendmail(msg['From'], [msg['To']], msg.as_string())
    s.quit()

def post2discord(message):
    req = urllib2.Request('https://discordapp.com/api/webhooks/XXXX')
    req.add_header('User-Agent', 'Hackers-Edge/1.0')
    req.add_header('Content-Type', 'application/json')
    req.add_data(json.dumps({'content':message}))
    try:
        r = urllib2.urlopen(req)
    except:
        return False
    if r.code != 204:
        return False
    return True
