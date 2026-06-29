from rest_framework.throttling import UserRateThrottle


class ChatbotRateThrottle(UserRateThrottle):
    scope = "chatbot"
