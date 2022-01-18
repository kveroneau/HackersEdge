from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
from databases import userdb
from settings import XMLRPC_TOKEN
import logging, hashlib

log = logging.getLogger('XMLRPC')

dispatcher = SimpleXMLRPCDispatcher()

TOKEN = hashlib.md5(XMLRPC_TOKEN).hexdigest()

class BetaAPI(object):
    def add_user(self, token, username, data):
        if token != TOKEN:
            return False
        log.info('Adding user: %s' % username)
        userdb[username] = data
        return True
    def del_user(self, token, username):
        if token != TOKEN:
            return False
        log.info('Removing user: %s' % username)
        try:
            del userdb[username]
            return True
        except KeyError:
            return False
    def get_user(self, token, username):
        if token != TOKEN:
            return False
        log.info('User data requested: %s' % username)
        try:
            return userdb[username]
        except KeyError:
            return False
    def chk_username(self, token, username):
        if token != TOKEN:
            return False
        return False if username in userdb else True

dispatcher.register_instance(BetaAPI())
