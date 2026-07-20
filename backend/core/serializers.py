from rest_framework import serializers

from core.services.keycloak_admin_service import APP_ROLES


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


class UserWriteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=120)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    first_name = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=120
    )
    last_name = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=120
    )
    password = serializers.CharField(min_length=6, write_only=True)
    role = serializers.ChoiceField(choices=[(r, r) for r in APP_ROLES])
    enabled = serializers.BooleanField(required=False, default=True)


class UserPatchSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    password = serializers.CharField(
        required=False, allow_blank=True, min_length=6, write_only=True
    )
    role = serializers.ChoiceField(choices=[(r, r) for r in APP_ROLES], required=False)
    enabled = serializers.BooleanField(required=False)

    def validate(self, attrs: dict) -> dict:
        if "password" in attrs and attrs["password"] == "":
            attrs.pop("password")
        if not attrs:
            raise serializers.ValidationError("Provide at least one updatable field")
        return attrs
