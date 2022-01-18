from django.conf.urls import patterns, url, include
from accounts.game_service import service
from accounts.views import NewCharacter, CharacterList, DeleteCharacter,\
    RedeemInvite, CharacterPassword, InviteList
from django.contrib.auth.decorators import login_required

character_urls = patterns('accounts.views',
    url(r'^$', login_required(CharacterList.as_view()), name='character_list'),
    url(r'^Create$', login_required(NewCharacter.as_view()), name='create_character'),
    url(r'^Delete(?P<pk>\d+)$', login_required(DeleteCharacter.as_view()), name='delete_character'),
    url(r'^Password(?P<pk>\d+)$', login_required(CharacterPassword.as_view()), name='character_password'),
)

urlpatterns = patterns('accounts.views',
    url(r'^RPC$', service),
    url(r'^Characters/', include(character_urls)),
    url(r'^RedeemInvite$', login_required(RedeemInvite.as_view()), name='redeem_invite'),
    url(r'^Invites$', login_required(InviteList.as_view()), name='invite_list'),
    url(r'^CreateInvite$', 'create_invite', name='create_invite'),
    url(r'^QRCode.png', 'qr_code', name='qr_code'),
    url(r'^GoogleAuthenticator$', 'google_auth', name='setup_otp'),
    url(r'^Statistics$', 'statistics', name='statistics'),
    url(r'^PurgeAccount$', 'remove_account', name='remove_account'),
)
