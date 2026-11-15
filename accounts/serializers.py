from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    # Same fields as me_json, with the same fallbacks for a user who has no profile
    display_name = serializers.SerializerMethodField()
    is_grower = serializers.SerializerMethodField()
    is_buyer = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('username', 'display_name', 'is_grower', 'is_buyer', 'last_login')
        read_only_fields = fields

    def get_display_name(self, user):
        profile = getattr(user, 'profile', None)
        return profile.display_name if profile else user.username

    def get_is_grower(self, user):
        profile = getattr(user, 'profile', None)
        return profile.is_grower if profile else False

    def get_is_buyer(self, user):
        profile = getattr(user, 'profile', None)
        return profile.is_buyer if profile else False
