from django.urls import path

from . import views

app_name = "assistant_v1"

urlpatterns = [
    path("chat/messages/", views.chat_message_send_view, name="chat_message_send"),
]
