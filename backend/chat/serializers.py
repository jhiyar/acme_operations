from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(trim_whitespace=True)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    # Optional Redis/history key override — used by the eval harness; UI uses conversation_id.
    session_id = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        default="",
    )

    def validate_message(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("message is required")
        return value
