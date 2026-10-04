from django.urls import path

from .views import (
    RouterJobCancelView,
    RouterJobDetailView,
    RouterJobListView,
    RouterJobRestartView,
    RouterJobRetryView,
    RouterTaskDetailView,
    RouterTaskKillView,
    RouterTaskResetView,
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
    path("jobs/<int:pk>/", RouterJobDetailView.as_view(), name="router_job_detail"),
    path("jobs/<int:pk>/cancel/", RouterJobCancelView.as_view(), name="router_job_cancel"),
    path("jobs/<int:pk>/retry/", RouterJobRetryView.as_view(), name="router_job_retry"),
    path("jobs/<int:pk>/restart/", RouterJobRestartView.as_view(), name="router_job_restart"),
    path("tasks/<int:pk>/", RouterTaskDetailView.as_view(), name="router_task_detail"),
    path("tasks/<int:pk>/reset/", RouterTaskResetView.as_view(), name="router_task_reset"),
    path("tasks/<int:pk>/kill/", RouterTaskKillView.as_view(), name="router_task_kill"),
]
