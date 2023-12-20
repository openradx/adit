from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.db.models import Model

from .models import User


class ActiveGroupModelBackend(ModelBackend):
    def get_group_permissions(self, user_obj: User, obj: Model | None = None) -> set[str]:
        """Get permissions of the current active group.

        Overwrites the super method to get only the permissions of the active group.
        """
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()

        perm_cache_name = "_active_group_perm_cache"
        if not hasattr(self, perm_cache_name):
            if user_obj.is_superuser:
                perms = Permission.objects.all()
            else:
                active_group = user_obj.active_group
                if not active_group:
                    setattr(self, perm_cache_name, set())
                    return set()
                perms = Permission.objects.filter(group=user_obj.active_group)
            perms = perms.values_list("content_type__app_label", "codename").order_by()
            setattr(self, perm_cache_name, {"%s.%s" % (ct, name) for ct, name in perms})
        return getattr(self, perm_cache_name)
