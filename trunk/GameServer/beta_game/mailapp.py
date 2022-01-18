import logging
from utils import Shell, hecmd
from sessions import SHM
from databases import get_host
from exceptions import SwitchShell, ShellError, SwitchState
import mailops

log = logging.getLogger('HackerMail')

class HackerMail(Shell):
    intro = 'HackerMail v0.2.2 $Revision: 183 $'
    def __init__(self, username, engine):
        self.udata = SHM[username]
        self.host = self.udata['host']
        self.route = self.udata['route']
        self.username, self.engine = username, engine
        self.host_data = get_host(self.host)
        self.mbox = '%s:%s' % (self.host, self.username)
        try:
            mailops.transfer_mail(self.mbox)
        except:
            pass
        self.msgid = None
        self.state = 'shell'
        self.history = []
        self.hpos = 0
    def transmit(self, data):
        self.engine.transmit(data)
    def save_history(self):
        pass
    def get_prompt(self):
        return '%s>' % self.mbox
    def handle_command(self, *cmd):
        log.info('Command: %s' % cmd[0])
        if not self.parse_cmd('cmd', False, *cmd):
            self.transmit(' ** Bad command.')
        return self.state
    def cmd_help(self, args):
        self.show_help('cmd')
    def cmd_exit(self, args):
        """ Exits HackerMail """
        raise SwitchShell('HackerShell')
    def cmd_list(self, args):
        """ Displays a list of messages in your mailbox. """
        msgs = mailops.list_mail(self.mbox)
        if len(msgs) == 0:
            self.transmit('<Empty>')
            return
        for msg in msgs:
            self.transmit(msg)
    @hecmd('<msgid>', 1)
    def cmd_read(self, args):
        """ Reads a message by it's message ID. """
        try:
            msgid = int(args[0])
        except ValueError:
            self.transmit('Please provide the message ID in the form of a Base 10!')
            return
        msg = mailops.read_mail(self.mbox, msgid)
        if msg:
            self.transmit(msg.replace('\n', '\r\n'))
            self.msgid = msgid
            log.info('User read message: %s' % msgid)
        else:
            self.transmit('Message could not be found.')
    @hecmd('[msgid]')
    def cmd_delete(self, args):
        """ Purges a message from your mailbox. """
        if len(args) > 0:
            try:
                msgid = int(args[0])
            except ValueError:
                if ',' in args[0]:
                    for msgid in args[0].split(','):
                        try:
                            mailops.delete_mail(self.mbox, int(msgid))
                            self.transmit('Deleted message ID %s.' % msgid)
                        except:
                            pass
                else:
                    self.transmit('Please provide the message ID in the form of a Base 10!')
        else:
            msgid = self.msgid
            self.msgid = None
        log.info('User delete message %s' % msgid)
        if not mailops.delete_mail(self.mbox, msgid):
            self.transmit('Message not found.')
    @hecmd('<to> "<subject>"', 2)
    def cmd_send(self, args):
        """ Send someone on the Hacker's Edge network a message. """
        to, subject = args
        if '@' not in to:
            to += '@%s' % self.host
        self.transmit('Write your message and terminate with a period on a line by itself.')
        self.udata['compose_msg'] = False
        self.udata['compose_cb'] = self.cb_send
        self.udata['mail_data'] = (to, subject,)
        raise SwitchState('compose')
    def cb_send(self, body):
        self.state = 'shell'
        self.transmit('Sending message...')
        to, subject = self.udata['mail_data']
        del self.udata['mail_data']
        body += getattr(self, 'signature', '')
        frm = '%s@%s' % (self.username, self.host)
        if not mailops.send_mail(frm, to, subject, body):
            self.transmit('Server rejected message.')
        else:
            self.transmit('Message sent.')
            log.info('User send message to %s' % to)
        try:
            del self.signature
        except:
            pass
    def get_msgid(self, args):
        if len(args) == 1:
            try:
                msgid = int(args[0])
            except ValueError:
                raise ShellError('Please provide the message ID in the form of a Base 10!')
        elif len(args) > 1:
            raise ShellError('Please only specify 1 message ID.')
        elif self.msgid is not None:
            msgid = self.msgid
            self.msgid = None
        else:
            raise ShellError('Please specify which message you would like to reply to.')
            return None
        return msgid
    @hecmd('[msgid]')
    def cmd_reply(self, args):
        """ Reply to a specific message or to the last message read. """
        msgid = self.get_msgid(args)
        msg = mailops.get_mail(self.mbox, msgid)
        if msg is not False:
            to = msg['from']
            self.signature = '\n---------------------\n%s' % mailops.read_mail(self.mbox, msgid)
            self.cmd_send([to, 'RE: %s' % msg['subject']])
        else:
            self.transmit('Message was not found.')
