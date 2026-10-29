import io
import shutil
import tempfile
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import Profile

from .models import Forum, Reply


def make_user(username, display_name):
    user = User.objects.create_user(username, password="pass12345")
    Profile.objects.create(user=user, display_name=display_name)
    return user

def make_forum(author, **extra):
    data = {
        "title": "A question",
        "description": "Some description",
        "topic": Forum.Topic.PLANT_CARE,
    }
    data.update(extra)
    return Forum.objects.create(author=author, **data)

def image_file(name="photo.png", fmt="PNG", content_type="image/png"):
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "green").save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

class ForumTestCase(TestCase):
    # two users, temporary MEDIA_ROOT so uploads don't touch media

    def setUp(self):
        media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        self.addCleanup(override.disable)

        self.alice = make_user("alice", "Alice Green")
        self.bob = make_user("bob", "Bob Brown")

    def assertLoginRedirect(self, response, url):
        self.assertRedirects(
            response, f"{settings.LOGIN_URL}?next={url}", fetch_redirect_response=False
        )

class ForumListTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.forum = make_forum(
            self.alice, title="Why yellow leaves", description="Secret body text"
        )
        self.url = reverse("forum:forum_list")

    def test_empty_state(self):
        Forum.objects.all().delete()
        response = self.client.get(self.url)
        self.assertContains(response, "No discussions yet")

    def test_visitor_sees_title_only(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Why yellow leaves")
        self.assertNotContains(response, "Secret body text")
        self.assertNotContains(response, "Alice Green")

    def test_member_sees_description_and_author(self):
        self.client.force_login(self.bob)
        response = self.client.get(self.url)
        self.assertContains(response, "Secret body text")
        self.assertContains(response, "Alice Green")

    def test_answer_count(self):
        Reply.objects.create(forum=self.forum, author=self.bob, body="One")
        Reply.objects.create(forum=self.forum, author=self.bob, body="Two")
        response = self.client.get(self.url)
        self.assertContains(response, "2 answers")

    def test_menu_only_for_author(self):
        edit_url = reverse("forum:forum_edit", args=[self.forum.pk])
        delete_url = reverse("forum:forum_delete", args=[self.forum.pk])

        self.client.force_login(self.alice)
        response = self.client.get(self.url)
        self.assertContains(response, edit_url)
        self.assertContains(response, delete_url)

        self.client.force_login(self.bob)
        response = self.client.get(self.url)
        self.assertNotContains(response, edit_url)
        self.assertNotContains(response, delete_url)

    def test_menu_hidden_for_visitor(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse("forum:forum_edit", args=[self.forum.pk]))

class ForumDetailTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.forum = make_forum(self.alice, description="Full discussion text")
        self.url = reverse("forum:forum_detail", args=[self.forum.pk])

    def test_visitor_redirected_to_login(self):
        self.assertLoginRedirect(self.client.get(self.url), self.url)

    def test_member_sees_discussion_and_replies(self):
        Reply.objects.create(forum=self.forum, author=self.bob, body="Try less water")
        self.client.force_login(self.bob)
        response = self.client.get(self.url)
        self.assertContains(response, "Full discussion text")
        self.assertContains(response, "Try less water")
        self.assertContains(response, "1 answer")

    def test_no_replies_message(self):
        self.client.force_login(self.bob)
        self.assertContains(self.client.get(self.url), "No answers yet.")

    def test_missing_post_is_404(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("forum:forum_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_menu_only_for_author(self):
        edit_url = reverse("forum:forum_edit", args=[self.forum.pk])

        self.client.force_login(self.alice)
        self.assertContains(self.client.get(self.url), edit_url)

        self.client.force_login(self.bob)
        self.assertNotContains(self.client.get(self.url), edit_url)

class ForumCreateTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("forum:forum_create")
        self.data = {
            "title": "My tomatoes",
            "description": "They keep splitting",
            "topic": "plant_care",
        }

    def test_visitor_redirected_to_login(self):
        self.assertLoginRedirect(self.client.get(self.url), self.url)
        self.assertLoginRedirect(self.client.post(self.url, self.data), self.url)
        self.assertEqual(Forum.objects.count(), 0)

    def test_form_page_loads(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create New Post")

    def test_valid_post_creates_forum_for_current_user(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, self.data)
        forum = Forum.objects.get()
        self.assertEqual(forum.author, self.alice)
        self.assertEqual(forum.title, "My tomatoes")
        self.assertRedirects(response, reverse("forum:forum_detail", args=[forum.pk]))

    def test_title_is_required(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, {**self.data, "title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "title", "Title can’t be empty")
        self.assertEqual(Forum.objects.count(), 0)

    def test_description_is_required(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, {**self.data, "description": ""})
        self.assertFormError(
            response.context["form"], "description", "Description can’t be empty"
        )

    def test_topic_is_required(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, {**self.data, "topic": ""})
        self.assertFormError(response.context["form"], "topic", "Select a topic")

    def test_author_cannot_be_forged(self):
        self.client.force_login(self.alice)
        self.client.post(self.url, {**self.data, "author": self.bob.pk})
        self.assertEqual(Forum.objects.get().author, self.alice)

    def test_image_upload(self):
        self.client.force_login(self.alice)
        self.client.post(self.url, {**self.data, "image": image_file()})
        forum = Forum.objects.get()
        self.assertTrue(forum.image)
        self.assertTrue(default_storage.exists(forum.image.name))

    def test_rejects_wrong_image_type(self):
        self.client.force_login(self.alice)
        gif = image_file("anim.gif", "GIF", "image/gif")
        response = self.client.post(self.url, {**self.data, "image": gif})
        self.assertFormError(
            response.context["form"], "image", "Upload a JPG, JPEG, PNG, or WEBP image."
        )
        self.assertEqual(Forum.objects.count(), 0)

    def test_rejects_large_image(self):
        self.client.force_login(self.alice)
        with mock.patch("forum.forms.MAX_IMAGE_BYTES", 10):
            response = self.client.post(self.url, {**self.data, "image": image_file()})
        self.assertFormError(response.context["form"], "image", "Image must be 5 MB or smaller.")
        self.assertEqual(Forum.objects.count(), 0)

class ForumEditTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.forum = make_forum(self.alice, title="Old title", description="Old body")
        self.url = reverse("forum:forum_edit", args=[self.forum.pk])
        self.detail_url = reverse("forum:forum_detail", args=[self.forum.pk])
        self.data = {"title": "New title", "description": "New body", "topic": "weather"}

    def test_visitor_redirected_to_login(self):
        self.assertLoginRedirect(self.client.get(self.url), self.url)
        self.assertLoginRedirect(self.client.post(self.url, self.data), self.url)

    def test_non_owner_gets_403(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.forum.refresh_from_db()
        self.assertEqual(self.forum.title, "Old title")

    def test_owner_sees_prefilled_form(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.url)
        self.assertContains(response, "Edit Post")
        self.assertContains(response, "Old title")
        self.assertContains(response, "Old body")

    def test_owner_can_edit(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, self.data)
        self.assertRedirects(response, self.detail_url)
        self.forum.refresh_from_db()
        self.assertEqual(self.forum.title, "New title")
        self.assertEqual(self.forum.topic, "weather")
        self.assertEqual(self.forum.author, self.alice)

    def test_invalid_edit_stays_on_form(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, {**self.data, "title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "title", "Title can’t be empty")
        self.forum.refresh_from_db()
        self.assertEqual(self.forum.title, "Old title")

    def test_defaults_to_detail_page(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.url)
        self.assertEqual(response.context["next_url"], self.detail_url)

    def test_next_is_used_for_cancel_and_redirect(self):
        self.client.force_login(self.alice)
        next_url = "/forum/?topic=weather"
        response = self.client.get(self.url, {"next": next_url})
        self.assertEqual(response.context["next_url"], next_url)

        response = self.client.post(self.url, {**self.data, "next": next_url})
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, {**self.data, "next": "https://evil.example/"})
        self.assertRedirects(response, self.detail_url)

    def test_has_image_flag(self):
        self.client.force_login(self.alice)
        self.assertFalse(self.client.get(self.url).context["has_image"])

        self.forum.image = image_file()
        self.forum.save()
        self.assertTrue(self.client.get(self.url).context["has_image"])

    def test_keeps_image_when_untouched(self):
        self.forum.image = image_file()
        self.forum.save()
        name = self.forum.image.name

        self.client.force_login(self.alice)
        self.client.post(self.url, self.data)
        self.forum.refresh_from_db()
        self.assertEqual(self.forum.image.name, name)
        self.assertTrue(default_storage.exists(name))

    def test_remove_image_deletes_file(self):
        self.forum.image = image_file()
        self.forum.save()
        name = self.forum.image.name

        self.client.force_login(self.alice)
        self.client.post(self.url, {**self.data, "remove_image": "1"})
        self.forum.refresh_from_db()
        self.assertFalse(self.forum.image)
        self.assertFalse(default_storage.exists(name))

    def test_replace_image_deletes_old_file(self):
        self.forum.image = image_file("old.png")
        self.forum.save()
        old_name = self.forum.image.name

        self.client.force_login(self.alice)
        self.client.post(self.url, {**self.data, "image": image_file("new.png")})
        self.forum.refresh_from_db()
        self.assertNotEqual(self.forum.image.name, old_name)
        self.assertTrue(default_storage.exists(self.forum.image.name))
        self.assertFalse(default_storage.exists(old_name))

    def test_new_upload_wins_over_remove_flag(self):
        self.forum.image = image_file("old.png")
        self.forum.save()

        self.client.force_login(self.alice)
        self.client.post(
            self.url, {**self.data, "remove_image": "1", "image": image_file("new.png")}
        )
        self.forum.refresh_from_db()
        self.assertTrue(self.forum.image)
        self.assertTrue(default_storage.exists(self.forum.image.name))

class ForumDeleteTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.forum = make_forum(self.alice)
        self.url = reverse("forum:forum_delete", args=[self.forum.pk])
        self.list_url = reverse("forum:forum_list")

    def test_visitor_redirected_to_login(self):
        self.assertLoginRedirect(self.client.post(self.url), self.url)
        self.assertTrue(Forum.objects.filter(pk=self.forum.pk).exists())

    def test_get_is_not_allowed(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertTrue(Forum.objects.filter(pk=self.forum.pk).exists())

    def test_non_owner_gets_403(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertTrue(Forum.objects.filter(pk=self.forum.pk).exists())

    def test_owner_can_delete(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url)
        self.assertRedirects(response, self.list_url)
        self.assertFalse(Forum.objects.filter(pk=self.forum.pk).exists())

    def test_replies_are_deleted_too(self):
        Reply.objects.create(forum=self.forum, author=self.bob, body="An answer")
        self.client.force_login(self.alice)
        self.client.post(self.url)
        self.assertEqual(Reply.objects.count(), 0)

    def test_image_file_is_removed(self):
        self.forum.image = image_file()
        self.forum.save()
        name = self.forum.image.name

        self.client.force_login(self.alice)
        self.client.post(self.url)
        self.assertFalse(default_storage.exists(name))

    def test_next_is_used(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, {"next": "/forum/?topic=weather"})
        self.assertRedirects(response, "/forum/?topic=weather", fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url, {"next": "https://evil.example/"})
        self.assertRedirects(response, self.list_url)