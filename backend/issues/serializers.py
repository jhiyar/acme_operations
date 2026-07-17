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
