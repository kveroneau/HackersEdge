import logging, asyncore

log = logging.getLogger('Sessions')

def notify_sessions(message, me, alt_message=None, sid_list=None):
    for s in asyncore.socket_map.values():
        if s.connected and hasattr(s, 'ctype') and hasattr(s, 'sid'):
            if s.sid != me:
                if sid_list is None or s.sid in sid_list:
                    s.notify(message)
            else:
                if alt_message:
                    s.notify(alt_message)

def player_count():
    count = 0
    for s in asyncore.socket_map.values():
        if s.connected and hasattr(s, 'username') and s.username is not None:
            count+=1
    return count

def is_connected(username):
    count = 0
    for s in asyncore.socket_map.values():
        if s.connected and hasattr(s, 'udata'):
            if not s.udata.has_key('username'):
                return False
            if s.udata['username'] == username:
                if s.state != 'login':
                    if s.udata['staff']:
                        s.handle_close()
                    else:
                        s.notify(' ** Attempted login from another location.')
                    count+=1
    if count > 0:
        return True
    return False

def connected_users():
    player_list = []
    for s in asyncore.socket_map.values():
        if s.connected and hasattr(s, 'sid'):
            if s.state != 'login':
                player_list.append(s.sid)
    return player_list

def kick_all():
    for s in asyncore.socket_map.values():
        if s.connected and hasattr(s, 'ctype') and hasattr(s, 'sid'):
            if not s.udata['staff']:
                s.handle_close()

def vm_list():
    vms = []
    for s in asyncore.socket_map.values():
        if s.connected and hasattr(s, 'endpoint'):
            vms.append(s.endpoint)
    return vms
