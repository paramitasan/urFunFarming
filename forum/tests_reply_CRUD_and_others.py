from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile

from .models import Forum, ForumVote, Reply, ReplyVote
from .templatetags.forum_tags import recent_forums

User = get_user_model()


def make_user(username):
    user = User.objects.create_user(username, password="pass12345")
    # update_or_create works whether or not a signal already made the profile
    Profile.objects.update_or_create(user=user, defaults={"display_name": username.title()})
    return user


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user("alice")
        cls.bob = make_user("bob")
        cls.carol = make_user("carol")

    def login(self, user):
        self.client.force_login(user)

    def make_forum(self, title="Some question", author=None, days_ago=0, **extra):
        extra.setdefault("description", "Some description")
        forum = Forum.objects.create(title=title, author=author or self.alice, **extra)
        # created_at is auto_now_add, so move both timestamps with update()
        stamp = timezone.now() - timedelta(days=days_ago)
        Forum.objects.filter(pk=forum.pk).update(created_at=stamp, updated_at=stamp)
        forum.refresh_from_db()
        return forum

    def make_reply(self, forum, body="An answer", author=None, days_ago=0):
        reply = Reply.objects.create(forum=forum, body=body, author=author or self.bob)
        stamp = timezone.now() - timedelta(days=days_ago)
        Reply.objects.filter(pk=reply.pk).update(created_at=stamp, updated_at=stamp)
        reply.refresh_from_db()
        return reply

    def assert_login_redirect(self, response, url):
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )


class ReplyCreateTests(BaseTestCase):
    def test_member_can_create_reply(self):
        forum = self.make_forum()
        self.login(self.bob)
        response = self.client.post(
            reverse("forum:reply_create", args=[forum.pk]), {"body": "Try less water"}
        )
        reply = Reply.objects.get()
        self.assertEqual((reply.forum, reply.author, reply.body), (forum, self.bob, "Try less water"))
        self.assertEqual(
            response["Location"],
            f"{reverse('forum:forum_detail', args=[forum.pk])}#reply-{reply.pk}",
        )

    def test_empty_and_whitespace_body_rejected(self):
        forum = self.make_forum()
        self.login(self.bob)
        url = reverse("forum:reply_create", args=[forum.pk])
        for body in ("", "    "):
            response = self.client.post(url, {"body": body})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Answer can’t be empty")
        self.assertEqual(Reply.objects.count(), 0)

    def test_get_not_allowed(self):
        forum = self.make_forum()
        self.login(self.bob)
        response = self.client.get(reverse("forum:reply_create", args=[forum.pk]))
        self.assertEqual(response.status_code, 405)

    def test_anonymous_redirected_to_login(self):
        forum = self.make_forum()
        url = reverse("forum:reply_create", args=[forum.pk])
        response = self.client.post(url, {"body": "Hello"})
        self.assert_login_redirect(response, url)
        self.assertEqual(Reply.objects.count(), 0)

    def test_reply_to_missing_forum_is_404(self):
        self.login(self.bob)
        response = self.client.post(reverse("forum:reply_create", args=[9999]), {"body": "Hi"})
        self.assertEqual(response.status_code, 404)


class ReplyEditTests(BaseTestCase):
    def setUp(self):
        self.forum = self.make_forum()
        self.reply = self.make_reply(self.forum, "old", self.bob, days_ago=1)
        self.url = reverse("forum:reply_edit", args=[self.reply.pk])

    def test_author_sees_edit_card(self):
        self.login(self.bob)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["editing_id"], self.reply.pk)
        self.assertContains(response, "Save changes")

    def test_author_can_save(self):
        self.login(self.bob)
        response = self.client.post(self.url, {"body": "new"})
        self.reply.refresh_from_db()
        self.assertEqual(self.reply.body, "new")
        self.assertEqual(response.status_code, 302)

    def test_empty_body_keeps_edit_mode(self):
        self.login(self.bob)
        response = self.client.post(self.url, {"body": " "})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Answer can’t be empty")
        self.reply.refresh_from_db()
        self.assertEqual(self.reply.body, "old")

    def test_edited_only_when_something_changed(self):
        self.login(self.bob)
        self.client.post(self.url, {"body": "old"})     # same text
        self.reply.refresh_from_db()
        self.assertFalse(self.reply.is_edited)

        self.client.post(self.url, {"body": "new"})
        self.reply.refresh_from_db()
        self.assertTrue(self.reply.is_edited)

    def test_other_member_gets_403(self):
        self.login(self.carol)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"body": "hacked"}).status_code, 403)
        self.reply.refresh_from_db()
        self.assertEqual(self.reply.body, "old")

    def test_forum_author_cannot_edit_someone_elses_reply(self):
        self.login(self.alice)   # alice owns the forum, bob owns the reply
        self.assertEqual(self.client.post(self.url, {"body": "hacked"}).status_code, 403)

    def test_anonymous_redirected(self):
        self.assert_login_redirect(self.client.get(self.url), self.url)


class ReplyDeleteTests(BaseTestCase):
    def setUp(self):
        self.forum = self.make_forum()
        self.reply = self.make_reply(self.forum, "bye", self.bob)
        self.url = reverse("forum:reply_delete", args=[self.reply.pk])

    def test_author_can_delete(self):
        self.login(self.bob)
        response = self.client.post(self.url)
        self.assertFalse(Reply.objects.filter(pk=self.reply.pk).exists())
        self.assertTrue(Forum.objects.filter(pk=self.forum.pk).exists())
        self.assertEqual(response.status_code, 302)

    def test_get_not_allowed(self):
        self.login(self.bob)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertTrue(Reply.objects.filter(pk=self.reply.pk).exists())

    def test_other_member_gets_403(self):
        self.login(self.carol)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertTrue(Reply.objects.filter(pk=self.reply.pk).exists())

    def test_anonymous_redirected(self):
        response = self.client.post(self.url)
        self.assert_login_redirect(response, self.url)
        self.assertTrue(Reply.objects.filter(pk=self.reply.pk).exists())

    def test_votes_deleted_with_reply(self):
        ReplyVote.objects.create(reply=self.reply, user=self.carol)
        self.login(self.bob)
        self.client.post(self.url)
        self.assertEqual(ReplyVote.objects.count(), 0)


class EditedLabelTests(BaseTestCase):
    """Regression: (edited) must follow each item's own timestamps."""

    def test_new_reply_in_edited_forum_is_not_marked(self):
        forum = self.make_forum(days_ago=1)
        Forum.objects.filter(pk=forum.pk).update(updated_at=timezone.now())   # forum edited
        self.make_reply(forum, "fresh")
        self.login(self.bob)
        response = self.client.get(reverse("forum:forum_detail", args=[forum.pk]))
        self.assertContains(response, "(edited)", count=1)   # the post only

    def test_edited_reply_in_unedited_forum_is_marked(self):
        forum = self.make_forum(days_ago=1)
        reply = self.make_reply(forum, "x", days_ago=1)
        Reply.objects.filter(pk=reply.pk).update(updated_at=timezone.now())
        self.login(self.bob)
        response = self.client.get(reverse("forum:forum_detail", args=[forum.pk]))
        self.assertContains(response, "(edited)", count=1)   # the reply only


class ForumListTests(BaseTestCase):
    def setUp(self):
        self.login(self.bob)

    def titles(self, **params):
        response = self.client.get(reverse("forum:forum_list"), params)
        self.assertEqual(response.status_code, 200)
        return [f.title for f in response.context["page_obj"]]

    # sort
    def make_sortable(self):
        old = self.make_forum("old", days_ago=3)
        mid = self.make_forum("mid", days_ago=2)
        new = self.make_forum("new", days_ago=1)
        for forum, n in ((old, 0), (mid, 2), (new, 1)):
            for i in range(n):
                self.make_reply(forum, f"r{i}")
        for forum, voters in ((old, [self.bob, self.carol]), (mid, [self.bob])):
            for user in voters:
                ForumVote.objects.create(forum=forum, user=user)

    def test_sort_newest_is_default(self):
        self.make_sortable()
        self.assertEqual(self.titles(), ["new", "mid", "old"])
        self.assertEqual(self.titles(sort="newest"), ["new", "mid", "old"])

    def test_sort_oldest(self):
        self.make_sortable()
        self.assertEqual(self.titles(sort="oldest"), ["old", "mid", "new"])

    def test_sort_most_answers(self):
        self.make_sortable()
        self.assertEqual(self.titles(sort="answers"), ["mid", "new", "old"])

    def test_sort_most_asked(self):
        self.make_sortable()
        self.assertEqual(self.titles(sort="asked"), ["old", "mid", "new"])

    def test_invalid_sort_falls_back_to_newest(self):
        self.make_sortable()
        self.assertEqual(self.titles(sort="bogus"), ["new", "mid", "old"])

    def test_votes_and_replies_do_not_multiply_each_other(self):
        forum = self.make_forum("busy")
        for i in range(3):
            self.make_reply(forum, f"r{i}")
        ForumVote.objects.create(forum=forum, user=self.bob)
        ForumVote.objects.create(forum=forum, user=self.carol)
        card = self.client.get(reverse("forum:forum_list")).context["page_obj"][0]
        self.assertEqual((card.reply_count, card.vote_count), (3, 2))

    # search
    def test_search_matches_every_word_in_title(self):
        self.make_forum("Yellow pak choy leaves")
        self.make_forum("Lettuce EC in NFT")
        self.assertEqual(self.titles(q="pak choy"), ["Yellow pak choy leaves"])
        self.assertEqual(self.titles(q="LETTUCE"), ["Lettuce EC in NFT"])
        self.assertEqual(self.titles(q="choy lettuce"), [])

    def test_member_search_includes_description(self):
        self.make_forum("Plain title", description="needs more nitrogen")
        self.assertEqual(self.titles(q="nitrogen"), ["Plain title"])

    # topic filter and counts
    def test_topic_filter(self):
        self.make_forum("w1", topic=Forum.Topic.WEATHER)
        self.make_forum("w2", topic=Forum.Topic.WEATHER)
        self.make_forum("s1", topic=Forum.Topic.SEEDLINGS)
        self.assertEqual(sorted(self.titles(topic="weather")), ["w1", "w2"])
        self.assertEqual(self.titles(topic="seedlings"), ["s1"])

    def test_invalid_topic_shows_everything(self):
        self.make_forum("a")
        self.make_forum("b")
        self.assertEqual(len(self.titles(topic="bogus")), 2)

    def test_topic_counts_follow_search_but_not_topic(self):
        self.make_forum("rain tips", topic=Forum.Topic.WEATHER)
        self.make_forum("rain gear", topic=Forum.Topic.WEATHER)
        self.make_forum("seedling light", topic=Forum.Topic.SEEDLINGS)
        response = self.client.get(reverse("forum:forum_list"), {"q": "rain", "topic": "weather"})
        counts = {t["value"]: t["count"] for t in response.context["topics"]}
        self.assertEqual(counts["weather"], 2)
        self.assertEqual(counts["seedlings"], 0)
        self.assertEqual(response.context["all_count"], 2)

    # "Show" filter
    def test_show_filters(self):
        done = self.make_forum("done", is_answered=True)
        self.make_forum("open")
        self.make_forum("mine", author=self.bob)
        self.assertEqual(self.titles(show="answered"), ["done"])
        self.assertEqual(sorted(self.titles(show="unanswered")), ["mine", "open"])
        self.assertEqual(self.titles(show="mine"), ["mine"])

    def test_answered_is_set_by_author_not_by_replies(self):
        forum = self.make_forum("has reply")
        self.make_reply(forum)
        self.assertEqual(self.titles(show="answered"), [])
        self.assertEqual(self.titles(show="unanswered"), ["has reply"])

    # pagination
    def test_pagination_ten_per_page(self):
        Forum.objects.bulk_create(
            [Forum(title=f"Post {i}", description="x", author=self.alice) for i in range(25)]
        )
        response = self.client.get(reverse("forum:forum_list"))
        self.assertEqual(len(response.context["page_obj"]), 10)
        self.assertEqual(response.context["total"], 25)
        self.assertEqual(len(self.titles(page=3)), 5)

    def test_bad_page_numbers_do_not_crash(self):
        Forum.objects.bulk_create(
            [Forum(title=f"Post {i}", description="x", author=self.alice) for i in range(25)]
        )
        url = reverse("forum:forum_list")
        self.assertEqual(self.client.get(url, {"page": 999}).context["page_obj"].number, 3)
        self.assertEqual(self.client.get(url, {"page": "abc"}).context["page_obj"].number, 1)

    def test_page_links_keep_filters(self):
        Forum.objects.bulk_create(
            [Forum(title=f"Post {i}", description="x", author=self.alice,
                   topic=Forum.Topic.WEATHER) for i in range(12)]
        )
        response = self.client.get(reverse("forum:forum_list"), {"topic": "weather", "sort": "oldest"})
        self.assertContains(response, "topic=weather")
        self.assertContains(response, "page=2")


class ReplySortTests(BaseTestCase):
    def setUp(self):
        forum = self.make_forum()
        self.forum = forum
        r1 = self.make_reply(forum, "r1", days_ago=4)      # 0 votes
        r2 = self.make_reply(forum, "r2", days_ago=3)      # 2 votes
        r3 = self.make_reply(forum, "r3", days_ago=2)      # 1 vote
        r4 = self.make_reply(forum, "r4", days_ago=1)      # 1 vote
        for reply, voters in ((r2, [self.alice, self.carol]), (r3, [self.alice]), (r4, [self.carol])):
            for user in voters:
                ReplyVote.objects.create(reply=reply, user=user)
        self.login(self.bob)

    def bodies(self, **params):
        response = self.client.get(reverse("forum:forum_detail", args=[self.forum.pk]), params)
        self.assertEqual(response.status_code, 200)
        return [r.body for r in response.context["replies"]]

    def test_best_first_is_default_and_ties_go_to_older(self):
        self.assertEqual(self.bodies(), ["r2", "r3", "r4", "r1"])
        self.assertEqual(self.bodies(sort="best"), ["r2", "r3", "r4", "r1"])

    def test_oldest_first(self):
        self.assertEqual(self.bodies(sort="oldest"), ["r1", "r2", "r3", "r4"])

    def test_newest_first(self):
        self.assertEqual(self.bodies(sort="newest"), ["r4", "r3", "r2", "r1"])

    def test_invalid_sort_falls_back_to_best(self):
        self.assertEqual(self.bodies(sort="bogus"), ["r2", "r3", "r4", "r1"])


class VisitorAccessTests(BaseTestCase):
    def setUp(self):
        self.forum = self.make_forum(
            "Visible title", description="secret description", is_answered=True
        )
        for i in range(3):
            self.make_reply(self.forum, f"secret reply {i}")
        ForumVote.objects.create(forum=self.forum, user=self.bob)
        ForumVote.objects.create(forum=self.forum, user=self.carol)

    def test_list_shows_title_vote_count_and_answer_count(self):
        response = self.client.get(reverse("forum:forum_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible title")
        self.assertContains(response, '<span class="vote-count">2</span>', html=True)
        self.assertContains(response, "3 answers")

    def test_list_hides_description_author_and_vote_button(self):
        response = self.client.get(reverse("forum:forum_list"))
        self.assertNotContains(response, "secret description")
        self.assertNotContains(response, "secret reply")
        self.assertNotContains(response, "Alice")
        self.assertNotContains(response, "data-vote")
        self.assertNotContains(response, 'class="forum-menu"')

    def test_search_does_not_leak_descriptions(self):
        response = self.client.get(reverse("forum:forum_list"), {"q": "secret"})
        self.assertEqual(list(response.context["page_obj"]), [])

    def test_mine_filter_is_ignored(self):
        response = self.client.get(reverse("forum:forum_list"), {"show": "mine"})
        self.assertEqual(response.context["selected_show"], "")
        self.assertEqual(len(response.context["page_obj"]), 1)

    def test_detail_redirects_to_login(self):
        url = reverse("forum:forum_detail", args=[self.forum.pk])
        response = self.client.get(url)
        self.assert_login_redirect(response, url)
        self.assertNotContains(response, "secret", status_code=302)

    def test_cannot_create_forum(self):
        url = reverse("forum:forum_create")
        self.assert_login_redirect(self.client.get(url), url)
        response = self.client.post(url, {"title": "t", "description": "d", "topic": "other"})
        self.assert_login_redirect(response, url)
        self.assertEqual(Forum.objects.count(), 1)

    def test_cannot_post_vote_edit_or_delete(self):
        reply = self.forum.replies.first()
        blocked = [
            reverse("forum:reply_create", args=[self.forum.pk]),
            reverse("forum:reply_edit", args=[reply.pk]),
            reverse("forum:reply_delete", args=[reply.pk]),
            reverse("forum:forum_edit", args=[self.forum.pk]),
            reverse("forum:forum_delete", args=[self.forum.pk]),
            reverse("forum:forum_vote", args=[self.forum.pk]),
            reverse("forum:reply_vote", args=[reply.pk]),
            reverse("forum:forum_toggle_answered", args=[self.forum.pk]),
        ]
        for url in blocked:
            self.assert_login_redirect(self.client.post(url, {"body": "x"}), url)
        self.assertEqual(Forum.objects.count(), 1)
        self.assertEqual(Reply.objects.count(), 3)
        self.assertEqual(ForumVote.objects.count(), 2)
        self.assertEqual(ReplyVote.objects.count(), 0)

    def test_member_sees_everything_visitor_does_not(self):
        self.login(self.bob)
        response = self.client.get(reverse("forum:forum_list"))
        self.assertContains(response, "secret description")
        self.assertContains(response, "data-vote")
        detail = self.client.get(reverse("forum:forum_detail", args=[self.forum.pk]))
        self.assertContains(detail, "secret reply 0")


class RecentForumsTagTests(BaseTestCase):
    def test_returns_five_newest(self):
        for i in range(7):
            self.make_forum(f"q{i}", days_ago=7 - i)   # q6 is the newest
        titles = [f.title for f in recent_forums(5)]
        self.assertEqual(titles, ["q6", "q5", "q4", "q3", "q2"])

    def test_returns_fewer_when_fewer_exist(self):
        self.make_forum("only one")
        self.assertEqual(len(recent_forums(5)), 1)

    def test_includes_reply_count(self):
        forum = self.make_forum("q")
        self.make_reply(forum)
        self.make_reply(forum)
        self.assertEqual(recent_forums(5)[0].reply_count, 2)