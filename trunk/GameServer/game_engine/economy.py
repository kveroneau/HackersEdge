from connector import VMConnector
from settings import RANKING_SERVER, GET_BALANCE, ADD_BALANCE, XFR_BALANCE, XTO_BALANCE
from exceptions import BankError
import logging

log = logging.getLogger('Economy')

class EconomyManager(object):
    """ This class is responsible for managing the in-game economy. """
    version = 'Economy v0.2 $Rev: 326 $'
    def __init__(self):
        self.__cache = {}
        self.__reset()
    def __reset(self):
        self.__ranking = None
        self.__banks = {}
        self.__bqueue = {}
        self.__requests = {}
        self.__rid = 0
        self.__state = None
    def start(self):
        if self.__ranking is None:
            log.info('Starting the economy...')
            self.__ranking = VMConnector(self, RANKING_SERVER)
        else:
            log.critical('Tried to start economy twice!')
    def stop(self):
        self.__ranking.handle_close()
        for bank in self.__banks.values():
            bank.handle_close()
        self.__reset()
    def cache_xp(self, username):
        log.info('Obtaining ranking info for %s...' % username)
        rid = self.__get_request('xp:%s' % username)
        self.__get_xp(username, rid)
    def give_xp(self, username, xp):
        log.info('Giving %s experience points to %s.' % (xp, username))
        rid = self.__get_request('xp:%s' % username)
        self.__add_xp(username, xp & 0xff, rid)
    def __get_request(self, req):
        self.__rid+=1
        self.__requests[self.__rid % 0x100] = req
        return self.__rid % 0x100
    def __disco_bank(self, ip_addr):
        if ip_addr in self.__banks.keys():
            if self.__banks[ip_addr].connected:
                self.__banks[ip_addr].handle_close()
            del self.__banks[ip_addr]
            del self.__bqueue[ip_addr]
    def __disco_rank(self):
        if self.__ranking.connected:
            self.__ranking.handle_close()
        self.__ranking = None
    def __get_balance(self, server, username, rid):
        if server == RANKING_SERVER:
            rid = self.__get_request('xp:%s' % username)
            self.__get_xp(username, rid)
        elif server in self.__banks.keys():
            rid = self.__get_request('bal:%s' % username)
            self.__banks[server].vm_exec(GET_BALANCE, username, rid, 0)
        else:
            self.__banks[server] = VMConnector(self, server)
            self.__bqueue[server] = ['bal:%s' % username]
    def __transfer_credits(self, frm, to, amount):
        frm = frm.split(':')
        to = to.split(':')
        if frm[0] in self.__banks.keys():
            rid = self.__get_request('xfr:%s' % frm[1])
            self.__banks[frm[0]].vm_exec(XFR_BALANCE, frm[1], rid, amount)
        else:
            self.__banks[frm[0]] = VMConnector(self, frm[0])
            self.__bqueue[frm[0]] = ['xfr:%s:%s' % (frm[1], amount)]
        # TODO: The transfer to an account should be performed only after a success transfer from.
        if to[0] in self.__banks.keys():
            rid = self.__get_request('xto:%s' % to[1])
            self.__banks[to[0]].vm_exec(XTO_BALANCE, to[1], rid, amount)
        else:
            self.__banks[to[0]] = VMConnector(self, to[0])
            self.__bqueue[to[0]] = ['xto:%s:%s' % (to[1], amount)]
    def __get_xp(self, username, rid):
        if self.__ranking is None:
            return
        self.__ranking.vm_exec(GET_BALANCE, username, rid, 0)
    def __add_xp(self, username, xp, rid):
        if self.__ranking is None:
            return
        self.__ranking.vm_exec(ADD_BALANCE, username, rid, xp)
    def vm_result(self, result, ip_addr=None):
        log.debug('VM Result code for %s: %s' % (ip_addr, result))
        if ip_addr == RANKING_SERVER:
            if result == 'ONLINE':
                log.info('Ranking server connected.')
            elif result == 'OFFLINE':
                log.info('Ranking server not powered on.')
                self.__ranking.vm_boot()
            elif result == 'IPL':
                log.info('Ranking server connected.')
            elif result == 'BOOTFAIL':
                log.critical('Failed to boot the ranking server.')
                self.__disco_rank()
            elif result == 'HALT':
                log.info('Ranking server has been shutdown, attempting to boot.')
                self.__ranking.vm_boot()
            elif result == 'EXCPT':
                log.critical('An exception occurred on the ranking server!')
                self.__disco_rank()
            elif result == 'NOHOST':
                log.critical('Ranking server has been incorrect configured.')
                self.__disco_rank()
            elif result == 'TERM':
                log.critical('VM Termination!')
                self.__disco_rank()
            elif result == 'EXECOK':
                log.info('VM Execution request successful.')
            elif result == 'EXECER':
                log.critical('VM Execution request failed.')
            else:
                log.warning('Unhandled VM Result code for %s: %s' % (ip_addr, result))
        else:
            if ip_addr in self.__banks.keys():
                if result == 'ONLINE':
                    log.info('Banking server %s connected.' % ip_addr)
                    if len(self.__bqueue[ip_addr]) > 0:
                        req = self.__bqueue[ip_addr][0]
                        self.__bqueue[ip_addr].remove(req)
                        req = req.split(':')
                        if req[0] == 'bal':
                            rid = self.__get_request('bal:%s' % req[1])
                            self.__banks[ip_addr].vm_exec(GET_BALANCE, req[1], rid, 0)
                        elif req[0] == 'xfr':
                            rid = self.__get_request('xfr:%s' % req[1])
                            self.__banks[ip_addr].vm_exec(XFR_BALANCE, req[1], rid, int(req[2]))
                        elif req[0] == 'xto':
                            rid = self.__get_request('xto:%s' % req[1])
                            self.__banks[ip_addr].vm_exec(XTO_BALANCE, req[1], rid, int(req[2]))
                elif result == 'OFFLINE':
                    log.info('Banking server %s offline.' % ip_addr)
                    self.__disco_bank(ip_addr)
                elif result == 'HALT':
                    log.info('Banking server %s has been shutdown.' % ip_addr)
                    self.__disco_bank(ip_addr)
                elif result == 'EXCPT':
                    log.critical('Banking server %s had an exception occur!' % ip_addr)
                    self.__disco_bank(ip_addr)
                elif result == 'NOHOST':
                    log.info('Banking server %s does not exist!' % ip_addr)
                    self.__disco_bank(ip_addr)
                elif result == 'TERM':
                    self.__disco_bank(ip_addr)
                elif result == 'EXECOK':
                    log.info('VM Execution request successful.')
                elif result == 'EXECER':
                    log.critical('VM Execution request failed.')
    def exec_result(self, ip_addr, regA, regX, regY):
        log.debug('EXEC Result for %s [%s,%s,%s]' % (ip_addr, regA, regX, regY))
        try:
            req = self.__requests[regY]
            log.debug('Request info: %s' % req)
            req = req.split(':')
            if req[0] == 'xp':
                bal = regA+(regX << 8)
                self.__cache[req[1]] = bal
            elif req[0] == 'bal':
                bal = regA+(regX << 8)
            elif req[0] == 'xfr':
                bal = regA+(regX << 8)
            elif req[0] == 'xto':
                bal = regA+(regX << 8)
        except:
            log.warning('Exception when parsing request data!')
    def __getitem__(self, item):
        if item in self.__cache.keys():
            return self.__cache[item]
        raise BankError('Balance unavailable!')

economy = EconomyManager()
