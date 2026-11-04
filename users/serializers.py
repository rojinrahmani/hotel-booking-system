from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Guest data. `password` is write-only and optional on update.

    Staff flags (`is_staff`, `is_superuser`) are not exposed, so the API cannot
    grant admin access.
    """

    password = serializers.CharField(
        write_only=True,
        required=False,
        trim_whitespace=False,
        style={"input_type": "password"},
        validators=[validate_password],
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
            "id_card",
            "phone",
            "gender",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        if password is not None:
            instance.set_password(password)
        return super().update(instance, validated_data)


class UserCreateSerializer(UserSerializer):
    """Same fields as `UserSerializer`, but `password` is required."""

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
        validators=[validate_password],
    )

    def create(self, validated_data):
        # create_user hashes the password.
        return User.objects.create_user(**validated_data)
