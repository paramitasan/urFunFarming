from rest_framework import serializers

from forum.models import Forum, Reply


class AuthorSerializer(serializers.Serializer):
    # Public name only, never the email. Same fallbacks as the templates' {% firstof %}.
    username = serializers.CharField()
    display_name = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()

    def get_display_name(self, user):
        profile = getattr(user, 'profile', None)
        return (profile and profile.display_name) or user.username

    def get_initials(self, user):
        profile = getattr(user, 'profile', None)
        return (profile and profile.initials) or user.username[:2].upper()


class ForumVisitorSerializer(serializers.ModelSerializer):
    # What a visitor sees on the list page: no author, date, description or photo
    topic_label = serializers.CharField(source='get_topic_display', read_only=True)
    vote_count = serializers.IntegerField(read_only=True)
    reply_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Forum
        fields = ('id', 'title', 'topic', 'topic_label', 'is_answered', 'vote_count', 'reply_count')
        read_only_fields = fields


class ForumMemberSerializer(ForumVisitorSerializer):
    # What a signed-in user sees on the list page
    author = AuthorSerializer(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    user_voted = serializers.BooleanField(read_only=True)

    class Meta(ForumVisitorSerializer.Meta):
        fields = ForumVisitorSerializer.Meta.fields + (
            'description', 'image', 'author', 'created_at', 'is_edited', 'user_voted',
        )
        read_only_fields = fields


class ReplySerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    vote_count = serializers.IntegerField(read_only=True)
    user_voted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reply
        fields = ('id', 'body', 'author', 'created_at', 'updated_at', 'is_edited', 'vote_count', 'user_voted')
        read_only_fields = fields


class ForumDetailSerializer(ForumMemberSerializer):
    replies = serializers.SerializerMethodField()

    class Meta(ForumMemberSerializer.Meta):
        fields = ForumMemberSerializer.Meta.fields + ('updated_at', 'replies')
        read_only_fields = fields

    def get_replies(self, forum):
        # The view passes the replies already sorted and annotated with votes
        return ReplySerializer(self.context['replies'], many=True, context=self.context).data
