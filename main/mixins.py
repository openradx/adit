from django.contrib.auth.mixins import AccessMixin

class OwnerRequiredMixin(AccessMixin):
    """
        Verify that the user is the owner of the object. By default
        also superusers and staff may access the object.
        Should be added to a view class after LoginRequiredMixin.
    """
    allow_superuser_access = True
    allow_staff_access = True
    owner_accessor = 'user'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        check_owner = True
        if (self.allow_superuser_access and request.user.is_superuser 
                or self.allow_staff_access and request.user.is_staff):
            check_owner = False

        if check_owner and request.user != getattr(self.object, self.owner_accessor):
            self.handle_no_permission()

        return super(OwnerRequiredMixin, self).dispatch(request, *args, **kwargs)