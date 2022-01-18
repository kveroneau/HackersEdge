from django.core.cache import cache
from accounts.models import UserProfile
from django.contrib.auth.models import Group

def user_profile(req):
    game_access = cache.get('game_access_%s' % req.user.pk, None)
    if game_access is None:
        try:
            profile = UserProfile.objects.get(user=req.user)
            game_access = profile.game_access
        except:
            game_access = False
    cache.set('game_access_%s' % req.user.pk, game_access)
    return {'GAME_ACCESS':game_access}

def open_access(req):
    if req.user.pk is None:
        return {}
    profile_created = cache.get('has_profile_%s' % req.user.pk, None)
    if profile_created:
        return {'GAME_ACCESS':True}
    try:
        UserProfile.objects.get(user=req.user)
    except:
        beta_grp = Group.objects.get(name='Beta Testers')
        UserProfile.objects.create(user=req.user, game_access=True)
        req.user.groups.add(beta_grp)
        req.user.save()
        cache.set('has_profile_%s' % req.user.pk, True)
    return {'GAME_ACCESS':True}
