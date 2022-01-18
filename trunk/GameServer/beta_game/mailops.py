from databases import get_host_dir
from email.mime.text import MIMEText
from sessions import SHM
import os, mailbox, datetime, logging

log = logging.getLogger('MailOps')

def get_mail_dir(ip_addr):
    host_dir = get_host_dir(ip_addr)
    mail_dir = '%s/%s/mail' % (host_dir, ip_addr)
    try:
        os.stat(mail_dir)
    except:
        return False
    return mail_dir

def get_mbox(mbox):
    ip_addr, mboxf = mbox.split(':')
    mail_dir = get_mail_dir(ip_addr)
    if not mail_dir:
        return None
    mfile = '%s/%s' % (mail_dir, mboxf)
    try:
        os.stat(mfile)
        return mailbox.mbox(mfile)
    except:
        return None

def transfer_mail(mbox):
    new = get_mbox('%s.new' % mbox)
    mbox = get_mbox(mbox)
    new.lock()
    mbox.lock()
    for msg in new.itervalues():
        mbox.add(msg)
    mbox.flush()
    mbox.unlock()
    mbox.close()
    new.clear()
    new.flush()
    new.unlock()
    new.close()

def check_mail(mbox):
    msgs = 0
    mbox = get_mbox('%s.new' % mbox)
    if mbox is None:
        return msgs
    if len(mbox) > 0:
        msgs = len(mbox)
    mbox.close()
    return msgs

def list_mail(mbox):
    msgs = []
    mbox = get_mbox(mbox)
    if mbox is None:
        return msgs
    mbox.lock()
    for k,v in mbox.iteritems():
        msgs.append('%s: %s\t%s' % (k, v['from'], v['subject']))
    mbox.unlock()
    mbox.close()
    return msgs

def read_mail(mbox, msgid):
    mbox = get_mbox(mbox)
    if mbox is None:
        return False
    mbox.lock()
    msg = mbox.get(msgid)
    mbox.unlock()
    mbox.close()
    if msg is not None:
        return 'From: %s\nReceived: %s\nSubject: %s\n\n%s' % (msg['from'], msg['received'], msg['subject'], msg.get_payload())
    else:
        return False

def get_mail(mbox, msgid):
    mbox = get_mbox(mbox)
    if mbox is None:
        return False
    mbox.lock()
    msg = mbox.get(msgid)
    mbox.unlock()
    mbox.close()
    if msg is not None:
        return {'from':msg['from'], 'subject':msg['subject']}
    else:
        return False

def delete_mail(mbox, msgid):
    mbox = get_mbox(mbox)
    if mbox is None:
        return False
    mbox.lock()
    mbox.discard(msgid)
    mbox.flush()
    mbox.unlock()
    mbox.close()
    return True

def send_mail(frm, to, subject, body):
    user, ip_addr = to.split('@')
    mbox = get_mbox('%s:%s.new' % (ip_addr,user))
    if mbox is None:
        return False
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = frm
    msg['Received'] = '%s' % datetime.datetime.now()
    mbox.lock()
    mbox.add(msg)
    mbox.flush()
    mbox.unlock()
    mbox.close()
    try:
        c = SHM.sessions[SHM[user]['username']]
        c.notify('You got new mail.')
    except:
        pass
    log.info('Send mail from "%s" to "%s", subject: %s' % (frm, to, subject))
    return True

def redirect_mail(mbox, msgid, to):
    log.info('Redirect mail request from: %s' % mbox)
    mbox = get_mbox(mbox)
    if mbox is None:
        return False
    mbox.lock()
    msg = mbox.get(msgid)
    mbox.unlock()
    mbox.close()
    if msg is not None:
        user, ip_addr = to.split('@')
        mbox = get_mbox('%s:%s.new' % (ip_addr,user))
        if mbox is None:
            return False
        new_msg = MIMEText(msg.get_payload())
        new_msg['Subject'] = msg['subject']
        new_msg['From'] = msg['from']
        new_msg['Received'] = msg['received']
        mbox.lock()
        mbox.add(new_msg)
        mbox.flush()
        mbox.unlock()
        mbox.close()
        try:
            c = SHM.sessions[SHM[user]['username']]
            c.notify('You got new mail.')
        except:
            pass
        log.info('Redirect mail from "%s" to "%s", subject: %s' % (msg['from'], to, msg['subject']))
        return True
    else:
        return False
