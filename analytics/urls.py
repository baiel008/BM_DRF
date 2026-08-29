from django.urls import path

from . import views

urlpatterns = [
    path("stats/users/", views.PublicStatsAPIView.as_view(), name="stats_users"),
    path("staff/analytics/unlock/", views.AnalyticsUnlockAPIView.as_view(), name="analytics_unlock"),
    path("staff/analytics/summary/", views.AnalyticsSummaryAPIView.as_view(), name="analytics_summary"),
]
