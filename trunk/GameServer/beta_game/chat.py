from sessions import SHM
import socket, asynchat, logging

log = logging.getLogger('ChatSystem')

class ChatChannel(object):
    name = 'public'
    description = 'Public chat channel'
    def __init__(self):
        self.users = []
    def clean_users(self):
        for sid in self.users:
            if not SHM.sessions.has_key(sid):
                self.leave(sid)
    def notify(self, data, me):
        cleanup = False
        for sid in self.users:
            if me != sid:
                try:
                    SHM.sessions[sid].notify('[%s] %s' % (self.name, data))
                except KeyError:
                    cleanup = True
        if cleanup:
            self.clean_users()
    def say(self, message, me):
        log.info('[%s] %s says "%s"' % (self.name, me, message))
        for sid in self.users:
            if me != sid:
                try:
                    SHM.sessions[sid].notify('[%s] %s says, "%s"' % (self.name, me, message))
                except KeyError:
                    pass
            else:
                SHM.sessions[sid].transmit('[%s] You say, "%s"' % (self.name, message))
    def join(self, sid):
        log.info('[%s] %s joined.' % (self.name, sid))
        if sid not in self.users:
            self.notify('%s joined channel.' % sid, sid)
            self.users.append(sid)
    def leave(self, sid):
        log.info('[%s] %s left.' % (self.name, sid))
        if sid in self.users:
            self.users.remove(sid)
            self.notify('%s left the channel' % sid, sid)

class ircbot(asynchat.async_chat):
    def __init__(self, addr, channel, notify):
        asynchat.async_chat.__init__(self)
        self.addr = addr
        self.nick = 'HackersEdge'
        self.channel = channel
        self.okaymsg = ':%s MODE %s :+i' % (self.nick, self.nick)
        self.notify = notify
        self.set_terminator('\r\n')
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        log.info('Connecting to %s on port %s...' % addr)
        self.connect(addr)
        self.ibuffer = ''
        self.okay = False
    def handle_connect(self):
        log.info('Pushing NICK to IRC Server...')
        self.push('NICK %s\r' % self.nick)
        self.push('USER %s %s %s :HackersEdge IRC konnector\r' % (self.nick, self.nick, self.nick))
    def handle_close(self):
        if self.okay:
            log.info('IRC connection closed.')
            self.notify('IRC Connection lost, attempting to reconnect...', '')
            self.okay = False
            self.ibuffer = ''
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            log.info('Connecting to %s on port %s...' % self.addr)
            self.connect(self.addr)
    def say(self, message):
        if self.connected and self.okay:
            self.push('PRIVMSG #%s :%s\r' % (self.channel, message))
    def pm(self, who, message):
        self.push('PRIVMSG %s :%s\r' % (who, message))
    def collect_incoming_data(self, data):
        self.ibuffer += data
    def found_terminator(self):
        data = self.ibuffer.replace(self.terminator, '')
        self.ibuffer = ''
        #log.info('IRC Data: %s' % data)
        self.notify(data, '')
        if data[:4] == 'PING':
            self.push('PONG%s\r' % data[4:])
            return
        elif data.startswith(self.okaymsg):
            if self.channel == 'sdf':
                self.push('PART #helpdesk\r')
            self.okay = True
            self.push('JOIN #%s\r' % self.channel)
            self.say('Hello %s!  I am connected to Hacker\'s Edge.' % self.channel)
        elif self.okay and 'PRIVMSG' in data:
            if 'hackersedge' in data.lower():
                self.say("Join Hacker's Edge today @ www.hackers-edge.com")
                return
            try:
                i = data.index('#%s' % self.channel)
                self.notify('%s' % data[i:], '')
            except:
                pass

class IRCChannel(ChatChannel):
    def __init__(self):
        super(IRCChannel, self).__init__()
        self.irc = ircbot(self.addr, self.channel, self.notify)
    def say(self, message, me):
        super(IRCChannel, self).say(message, me)
        self.irc.say('%s says, "%s"' % (me, message))
    def join(self, sid):
        super(IRCChannel, self).join(sid)
        self.irc.say('%s has joined the channel.' % sid)
    def leave(self, sid):
        super(IRCChannel, self).leave(sid)
        self.irc.say('%s has left the channel.' % sid)

class SlimeSalad(IRCChannel):
    name = 'irc'
    addr = ('irc.esper.net', 6667)
    channel = 'slimesalad'
    description = 'A Channel connected to an IRC'    

class GopherChat(IRCChannel):
    name = 'gopher'
    addr = ('chat.freenode.net', 6667)
    channel = 'gopherproject'
    description = 'A Channel connected to #gopherproject'

class SDFChat(IRCChannel):
    name = 'sdf'
    addr = ('irc.sdf.org', 6667)
    channel = 'sdf'
    description = 'SDF IRC Chat channel'

class KernelChat(ChatChannel):
    name = 'kernel'
    description = 'KERNEL.SYS API and Development chat'

channels = {}
channels['public'] = ChatChannel()
channels['kernel'] = KernelChat()
#channels['sdf'] = SDFChat()
#channels['irc'] = SlimeSalad()
#channels['gopher'] = GopherChat()
