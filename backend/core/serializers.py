from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(trim_whitespace=True)

    def validate_message(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("message is required")
        return value


class AgentToolCallSerializer(serializers.Serializer):
    tool = serializers.CharField(trim_whitespace=True)
    args = serializers.DictField(required=False, default=dict)

    def validate_tool(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("tool is required")
        return value

    def validate_args(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError("args must be an object")
        return value
