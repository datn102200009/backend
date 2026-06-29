from rest_framework import serializers


class ChatMessageInputSerializer(serializers.Serializer):
    content = serializers.CharField(min_length=1, max_length=4000)
    conversation_history = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        max_length=10,
    )

    def validate_conversation_history(self, value):
        for turn in value:
            if not isinstance(turn, dict):
                raise serializers.ValidationError("Mỗi turn phải là object")
            role = turn.get("role")
            if role not in ("user", "assistant"):
                raise serializers.ValidationError("role phải là 'user' hoặc 'assistant'")
            if not isinstance(turn.get("content"), str):
                raise serializers.ValidationError("content phải là string")
        return value
