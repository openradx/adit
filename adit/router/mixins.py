from adit_radis_shared.common.types import AuthenticatedHttpRequest
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RouterStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Lets only staff in, even refusing a non-staff user who owns router jobs as a rule's creator.

    A routing rule is a standing export of patient data, so its pages, its jobs and their
    actions are for staff only.
    """

    request: AuthenticatedHttpRequest

    def test_func(self) -> bool:
        return self.request.user.is_staff
