from django.urls import path

from .views import (
    RouterJobListView,
    RoutingRuleDetailView,
    RoutingRuleListView,
    RoutingRuleRetryFailedView,
    RoutingRuleToggleView,
)

urlpatterns = [
    path("rules/", RoutingRuleListView.as_view(), name="router_rule_list"),
    path("rules/<int:pk>/", RoutingRuleDetailView.as_view(), name="router_rule_detail"),
    path("rules/<int:pk>/toggle/", RoutingRuleToggleView.as_view(), name="router_rule_toggle"),
    path(
        "rules/<int:pk>/retry-failed/",
        RoutingRuleRetryFailedView.as_view(),
        name="router_rule_retry_failed",
    ),
    path("jobs/", RouterJobListView.as_view(), name="router_job_list"),
]
