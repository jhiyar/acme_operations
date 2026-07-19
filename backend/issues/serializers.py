from rest_framework import serializers

from issues.models import Customer, Issue, IssueUpdate, NextAction


class IssueCustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    name = serializers.CharField()


class IssueUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueUpdate
        fields = ("id", "author", "body", "created_at")


class NextActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NextAction
        fields = ("id", "summary", "recommended_by", "status", "created_at")


class IssueSerializer(serializers.ModelSerializer):
    customer = IssueCustomerSerializer(read_only=True)

    class Meta:
        model = Issue
        fields = (
            "id",
            "title",
            "description",
            "status",
            "priority",
            "assigned_to",
            "customer",
            "created_at",
            "updated_at",
        )


class IssueDetailSerializer(IssueSerializer):
    updates = IssueUpdateSerializer(many=True, read_only=True)
    next_actions = NextActionSerializer(many=True, read_only=True)

    class Meta(IssueSerializer.Meta):
        fields = IssueSerializer.Meta.fields + ("updates", "next_actions")


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "id",
            "name",
            "industry",
            "tier",
            "account_owner",
            "contact_email",
            "notes",
        )


class IssuePatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=Issue.Status.choices,
        required=False,
    )
    priority = serializers.ChoiceField(
        choices=Issue.Priority.choices,
        required=False,
    )
    assigned_to = serializers.CharField(required=False, allow_blank=False, max_length=120)
    title = serializers.CharField(required=False, allow_blank=False, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    customer_id = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs: dict) -> dict:
        if not attrs:
            raise serializers.ValidationError(
                "Provide at least one updatable field"
            )
        return attrs


class IssueWriteSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=Issue.Status.choices,
        required=False,
        default=Issue.Status.OPEN,
    )
    priority = serializers.ChoiceField(
        choices=Issue.Priority.choices,
        required=False,
        default=Issue.Priority.MEDIUM,
    )
    assigned_to = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")


class IssueUpdateCreateSerializer(serializers.Serializer):
    body = serializers.CharField(trim_whitespace=True)

    def validate_body(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("body is required")
        return value
