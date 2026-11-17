import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Profile
from forum.models import Forum, ForumVote, Reply, ReplyVote
from forum.views import FORUMS_PER_PAGE

from .tests_forum_CRUD import image_file

VISITOR_FIELDS = {'id', 'title', 'topic', 'topic_label', 'is_answered', 'vote_count', 'reply_count'}
MEMBER_FIELDS = VISITOR_FIELDS | {'description', 'image', 'author', 'created_at', 'is_edited', 'user_voted'}
LIST_URL = reverse('forum_api:forum_list')


def make_user(username, display_name, email=''):
    user = User.objects.create_user(username, password='pass12345', email=email)
    Profile.objects.create(user=user, display_name=display_name)
    return user


def make_forum(author, **extra):
    data = {'title': 'A question', 'description': 'Some description', 'topic': Forum.Topic.PLANT_CARE}
    data.update(extra)
    return Forum.objects.create(author=author, **data)


class ForumApiTestCase(APITestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        self.addCleanup(override.disable)

        self.alice = make_user('alice', 'Alice Green', email='alice@example.com')
        self.bob = make_user('bob', 'Bob Brown', email='bob@example.com')

    def use_token(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=user).key}')

    def results(self, **params):
        response = self.client.get(LIST_URL, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data['results']


class ForumListVisitorTest(ForumApiTestCase):
    def test_visitor_sees_only_list_page_fields(self):
        forum = make_forum(self.alice, image=image_file())
        Reply.objects.create(forum=forum, author=self.bob, body='Water less')
        ForumVote.objects.create(forum=forum, user=self.bob)
        [item] = self.results()
        self.assertEqual(set(item), VISITOR_FIELDS)
        self.assertEqual(item['title'], 'A question')
        self.assertEqual(item['topic_label'], 'Plant care')
        self.assertEqual(item['reply_count'], 1)
        self.assertEqual(item['vote_count'], 1)

    def test_visitor_never_sees_author_or_description(self):
        make_forum(self.alice, description='secret-ish body text')
        content = self.client.get(LIST_URL).content.decode()
        self.assertNotIn('alice', content)
        self.assertNotIn('Alice Green', content)
        self.assertNotIn('secret-ish', content)

    def test_visitor_search_matches_titles_only(self):
        make_forum(self.alice, title='Tomato leaves', description='yellow spots')
        self.assertEqual(len(self.results(q='tomato')), 1)
        self.assertEqual(self.results(q='yellow'), [])

    def test_visitor_cannot_use_show_mine(self):
        make_forum(self.alice)
        self.assertEqual(len(self.results(show='mine')), 1)

    def test_bad_token_on_open_list_gives_401(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token not-a-real-token')
        self.assertEqual(self.client.get(LIST_URL).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_is_read_only(self):
        self.use_token(self.alice)
        response = self.client.post(LIST_URL, {'title': 'x'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertFalse(Forum.objects.exists())


class ForumListFilterTest(ForumApiTestCase):
    def test_topic_and_answered_filters(self):
        make_forum(self.alice, title='Wet', topic=Forum.Topic.HYDROPONICS, is_answered=True)
        make_forum(self.alice, title='Dry', topic=Forum.Topic.BALCONY)
        self.assertEqual([f['title'] for f in self.results(topic='hydroponics')], ['Wet'])
        self.assertEqual([f['title'] for f in self.results(show='answered')], ['Wet'])
        self.assertEqual([f['title'] for f in self.results(show='unanswered')], ['Dry'])

    def test_bad_filter_values_fall_back(self):
        make_forum(self.alice)
        self.assertEqual(len(self.results(topic='nope', show='nope', sort='nope')), 1)

    def test_sorts(self):
        older = make_forum(self.alice, title='Older')
        newer = make_forum(self.alice, title='Newer')
        Reply.objects.create(forum=older, author=self.bob, body='hi')
        ForumVote.objects.create(forum=older, user=self.bob)
        self.assertEqual([f['title'] for f in self.results()], ['Newer', 'Older'])
        self.assertEqual([f['title'] for f in self.results(sort='oldest')], ['Older', 'Newer'])
        self.assertEqual([f['title'] for f in self.results(sort='answers')], ['Older', 'Newer'])
        self.assertEqual([f['title'] for f in self.results(sort='asked')], ['Older', 'Newer'])
        self.assertEqual(newer.pk, self.results()[0]['id'])

    def test_pagination_and_bad_page_is_clamped(self):
        for i in range(FORUMS_PER_PAGE + 1):
            make_forum(self.alice, title=f'Q{i}')
        first = self.client.get(LIST_URL).data
        self.assertEqual((first['count'], first['page'], first['num_pages']), (FORUMS_PER_PAGE + 1, 1, 2))
        self.assertEqual(len(first['results']), FORUMS_PER_PAGE)
        last = self.client.get(LIST_URL, {'page': 99}).data
        self.assertEqual((last['page'], len(last['results'])), (2, 1))
        self.assertEqual(self.client.get(LIST_URL, {'page': 'abc'}).data['page'], 1)


class ForumListMemberTest(ForumApiTestCase):
    def test_member_sees_author_description_and_own_vote(self):
        forum = make_forum(self.alice, image=image_file())
        ForumVote.objects.create(forum=forum, user=self.bob)
        self.use_token(self.bob)
        [item] = self.results()
        self.assertEqual(set(item), MEMBER_FIELDS)
        self.assertEqual(item['author'], {'username': 'alice', 'display_name': 'Alice Green', 'initials': 'AG'})
        self.assertEqual(item['description'], 'Some description')
        self.assertTrue(item['image'].startswith('http://testserver/'))
        self.assertTrue(item['user_voted'])
        self.assertFalse(item['is_edited'])

    def test_member_never_sees_emails(self):
        make_forum(self.alice)
        self.use_token(self.bob)
        self.assertNotIn('@example.com', self.client.get(LIST_URL).content.decode())

    def test_member_search_matches_descriptions(self):
        make_forum(self.alice, title='Tomato leaves', description='yellow spots')
        self.use_token(self.bob)
        self.assertEqual(len(self.results(q='yellow')), 1)

    def test_show_mine(self):
        make_forum(self.alice, title='Mine')
        make_forum(self.bob, title='Theirs')
        self.use_token(self.alice)
        self.assertEqual([f['title'] for f in self.results(show='mine')], ['Mine'])

    def test_website_session_also_works(self):
        make_forum(self.alice)
        self.client.force_login(self.bob)
        self.assertEqual(set(self.results()[0]), MEMBER_FIELDS)

    def test_author_without_profile_falls_back_to_username(self):
        carol = User.objects.create_user('carol', password='pass12345')
        make_forum(carol)
        self.use_token(self.bob)
        self.assertEqual(self.results()[0]['author'], {'username': 'carol', 'display_name': 'carol', 'initials': 'CA'})

    def test_author_with_blank_display_name_falls_back_like_the_templates(self):
        Profile.objects.filter(user=self.alice).update(display_name='')
        make_forum(self.alice)
        self.use_token(self.bob)
        self.assertEqual(self.results()[0]['author'], {'username': 'alice', 'display_name': 'alice', 'initials': 'AL'})


class ForumDetailApiTest(ForumApiTestCase):
    def setUp(self):
        super().setUp()
        self.forum = make_forum(self.alice, description='Full text')
        self.url = reverse('forum_api:forum_detail', args=[self.forum.pk])

    def test_no_login_gives_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('Full text', response.content.decode())

    def test_bad_token_gives_401(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token not-a-real-token')
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_member_sees_post_and_replies(self):
        reply = Reply.objects.create(forum=self.forum, author=self.bob, body='Water less')
        ReplyVote.objects.create(reply=reply, user=self.alice)
        self.use_token(self.alice)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Full text')
        self.assertEqual(response.data['reply_count'], 1)
        self.assertIsNone(response.data['image'])
        [item] = response.data['replies']
        self.assertEqual(item['body'], 'Water less')
        self.assertEqual(item['author']['username'], 'bob')
        self.assertEqual(item['vote_count'], 1)
        self.assertTrue(item['user_voted'])
        self.assertNotIn('@example.com', response.content.decode())

    def test_reply_sorts_match_the_website(self):
        first = Reply.objects.create(forum=self.forum, author=self.bob, body='first')
        second = Reply.objects.create(forum=self.forum, author=self.bob, body='second')
        ReplyVote.objects.create(reply=second, user=self.alice)
        self.use_token(self.alice)

        def bodies(**params):
            return [r['body'] for r in self.client.get(self.url, params).data['replies']]

        self.assertEqual(bodies(), ['second', 'first'])             # best
        self.assertEqual(bodies(sort='oldest'), ['first', 'second'])
        self.assertEqual(bodies(sort='newest'), ['second', 'first'])
        self.assertEqual(bodies(sort='nope'), ['second', 'first'])
        self.assertEqual(first.pk, self.client.get(self.url, {'sort': 'oldest'}).data['replies'][0]['id'])

    def test_missing_post_gives_404(self):
        self.use_token(self.alice)
        response = self.client.get(reverse('forum_api:forum_detail', args=[self.forum.pk + 100]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_is_read_only(self):
        self.use_token(self.alice)
        self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Forum.objects.filter(pk=self.forum.pk).exists())
