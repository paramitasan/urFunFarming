# API login for the Flutter app

The Flutter app logs in with a **token**. The website keeps its normal session login, and nothing about it changes.

## Base URL

| Where the app runs | Base URL |
| --- | --- |
| Android emulator, Django on your laptop | `http://10.0.2.2:8000` |
| iOS simulator or desktop | `http://127.0.0.1:8000` |
| Deployed (PWS) | `https://paramita-santoso-urfunfarming.pws.cs.ui.ac.id` |

Start Django with `python manage.py runserver`. Run `python manage.py migrate` once first, because it creates the token table.

## Endpoints

| Method and path | Login needed | Body | Success |
| --- | --- | --- | --- |
| `POST /api/auth/register/` | no | `display_name`, `username`, `password1`, `password2`, `is_grower`, `is_buyer` | `201`, the user fields |
| `POST /api/auth/login/` | no | `username`, `password` | `200`, `token` and the user fields |
| `POST /api/auth/logout/` | token | none | `204`, and the token stops working |
| `GET /api/auth/me/` | token | none | `200`, the user fields |
| `GET /api/forum/` | no | `?q= &topic= &show= &sort= &page=` | `200`, a page of posts |
| `GET /api/forum/<id>/` | yes | `?sort=best\|oldest\|newest` | `200`, the post with its replies |

The **user fields** are `username`, `display_name`, `is_grower`, `is_buyer` and `last_login`. `last_login` is an ISO date, or `null` if the account has never logged in.

Register follows the same rules as the website's sign-up form, so at least one of `is_grower` and `is_buyer` must be true. Registering does not log you in. Call login next.

**Errors.** A form error comes back as `400` with the message under its field name. An error that isn't about one field, such as a wrong password or no role picked, is under `__all__`:

```json
{"errors": {"password2": ["The two password fields didn't match."]}}
{"errors": {"__all__": ["That username and password don't match. Check them and try again."]}}
```

A missing token, a wrong one, or one deleted by logging out gives `401` (`{"detail": "..."}`). When the app gets a 401, it should forget the token and show the login screen. A valid login without the right to do something gives `403`.

## The header

Every request after login sends the token in this header, with the word `Token`, one space, then the key:

```
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

`Bearer` does not work. The same token stays valid until the user logs out, and logging in again before that returns the same token.

## From Flutter

This example uses the `http` package. Save the token with `shared_preferences` or `flutter_secure_storage`, so the user stays logged in after closing the app.

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

const baseUrl = 'http://10.0.2.2:8000';

Future<String> login(String username, String password) async {
  final response = await http.post(
    Uri.parse('$baseUrl/api/auth/login/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'username': username, 'password': password}),
  );
  final data = jsonDecode(response.body);
  if (response.statusCode != 200) {
    throw Exception(data['errors']['__all__']?.first ?? 'Login failed');
  }
  return data['token'];   // save this
}

Future<Map<String, dynamic>> getForumPost(String token, int id) async {
  final response = await http.get(
    Uri.parse('$baseUrl/api/forum/$id/'),
    headers: {'Authorization': 'Token $token'},
  );
  if (response.statusCode == 401) {
    // token is gone: clear it and go back to the login screen
  }
  return jsonDecode(response.body);
}

Future<void> logout(String token) async {
  await http.post(
    Uri.parse('$baseUrl/api/auth/logout/'),
    headers: {'Authorization': 'Token $token'},
  );
}
```

## Protecting your own endpoint

Follow the same layout as the course's DRF tutorial. In your app, put views in `api_views.py`, routes in `api_urls.py` and serializers in `serializers.py`, then add your routes to `uff/urls.py` under `api/<your app>/`. The forum API (`forum/api_views.py`, `forum/tests_api.py`) is a complete example to copy from.

You don't need `@authentication_classes`. The project defaults accept a token, and a website session as a fallback. Pick who may call the view with `@permission_classes`:

| Who may call it | Permission |
| --- | --- |
| Everyone, even without logging in | `AllowAny` |
| Logged-in users | `IsAuthenticated` |
| Logged-in growers (`profile.is_grower`) | `IsGrower` |
| Anyone can read, only the owner can change | `IsOwnerOrReadOnly` and `check_object_permissions` |

`IsGrower`, `IsOwnerOrReadOnly` and `check_object_permissions` come from `accounts/permissions.py`. `AllowAny` and `IsAuthenticated` come from `rest_framework.permissions`.

This example shows what a gardens API could look like. `GardenSerializer` doesn't exist yet; you would write it in `gardens/serializers.py`.

```python
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsGrower, IsOwnerOrReadOnly, check_object_permissions
from gardens.models import Garden
from gardens.serializers import GardenSerializer


@api_view(['GET', 'POST'])
@permission_classes([IsGrower])
def garden_list_api(request):
    if request.method == 'POST':
        serializer = GardenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)   # the owner comes from the token, never from the body
        return Response(serializer.data, status=201)
    gardens = Garden.objects.filter(owner=request.user)
    return Response(GardenSerializer(gardens, many=True).data)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsOwnerOrReadOnly])
def garden_detail_api(request, pk):
    garden = get_object_or_404(Garden, pk=pk)
    check_object_permissions(request, garden)   # 403 for PUT/DELETE by someone else
    ...
```

Three things to watch:

1. **Call `check_object_permissions(request, obj)` in a function view.** `IsOwnerOrReadOnly` checks one object, and DRF only runs that check automatically in class-based views. If you leave the call out, anyone logged in can edit anything.
2. **`IsOwnerOrReadOnly` finds the owner by itself** from a field called `owner`, `author` or `user`. If your model is owned through another object, such as a journal entry through its garden, make a subclass:

   ```python
   class IsGardenOwnerOrReadOnly(IsOwnerOrReadOnly):
       def get_owner_id(self, obj):
           return obj.garden.owner_id
   ```

3. **Match the website's rules.** If a page uses `@login_required`, the API view needs `IsAuthenticated`. If a page shows less to visitors, give visitors a smaller serializer, like `ForumVisitorSerializer` in the forum example. Never put emails, passwords or tokens in a serializer.

For tests, use `APITestCase`. Log in with `self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')`, and check for 401 without a token and 403 for the wrong user (see `forum/tests_api.py` and `accounts/tests_permissions.py`).
