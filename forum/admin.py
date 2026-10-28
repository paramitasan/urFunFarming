from django.contrib import admin
from .models import Forum, Reply, ForumVote, ReplyVote

admin.site.register(Forum)
admin.site.register(Reply)
admin.site.register(ForumVote)
admin.site.register(ReplyVote)