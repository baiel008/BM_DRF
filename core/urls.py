from django.urls import path

from . import views

urlpatterns = [
    path("notifications/", views.NotificationListAPIView.as_view(), name="notification_list"),
    path("notifications/unread-count/", views.NotificationUnreadCountAPIView.as_view(), name="notification_unread_count"),
    path("notifications/mark-all-read/", views.NotificationMarkAllReadAPIView.as_view(), name="notification_mark_all"),
    path("notifications/<int:pk>/read/", views.NotificationMarkReadAPIView.as_view(), name="notification_read"),
    path("followed-shops/", views.FollowedShopsListAPIView.as_view(), name="followed_shops"),
    path("follows/toggle/<int:pk>/", views.FollowShopToggleAPIView.as_view(), name="follow_toggle"),
]
