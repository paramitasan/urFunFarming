from copy import copy
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers

from marketplace.forms import ListingForm
from marketplace.models import HarvestListing


class HarvestSerializer(serializers.ModelSerializer):
    """One public representation for cards and details; no contact data in lists."""

    owner_username = serializers.CharField(source='owner.username', read_only=True)
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = HarvestListing
        fields = (
            'id', 'title', 'description', 'category', 'quantity', 'unit', 'price',
            'price_quantity', 'price_label', 'price_unit_label', 'quantity_label',
            'status_label', 'area', 'city', 'image_url', 'available_from',
            'available_until', 'is_available', 'is_demo', 'grower_name',
            'owner_username', 'can_manage',
        )
        read_only_fields = fields

    def get_can_manage(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and user.pk == obj.owner_id


class MemberHarvestSerializer(HarvestSerializer):
    """Only used on a detail response after authentication."""

    contact = serializers.SerializerMethodField()

    class Meta(HarvestSerializer.Meta):
        fields = (*HarvestSerializer.Meta.fields, 'contact')
        read_only_fields = fields

    def get_contact(self, obj):
        profile = getattr(obj.owner, 'profile', None)
        return {
            'phone': profile.phone if profile else '',
            'email': profile.contact_email if profile else '',
        }


class HarvestWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HarvestListing
        # Same editable fields as the website; never accept owner or demo status.
        fields = ListingForm.Meta.fields

    def validate_image_url(self, value):
        if value and urlsplit(value).scheme not in ('http', 'https'):
            raise serializers.ValidationError('Use an HTTP or HTTPS image link.')
        return value

    def validate(self, attrs):
        # PATCH must validate the resulting record, including fields not sent.
        candidate = copy(self.instance) if self.instance is not None else HarvestListing()
        for name, value in attrs.items():
            setattr(candidate, name, value)
        try:
            candidate.clean()
        except ModelValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error
        return attrs
