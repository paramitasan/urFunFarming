"""Permission classes every app can use in its API views.

    from accounts.permissions import IsGrower, IsOwnerOrReadOnly, check_object_permissions

See docs/API_AUTH.md for examples.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsGrower(BasePermission):
    """Signed-in users whose profile has is_grower, like the website's grower-only pages.

    A request without a valid login gets 401, a signed-in buyer gets 403.
    """

    message = 'Only growers can do this. Turn on "I grow food" in your profile.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        profile = getattr(user, 'profile', None)
        return bool(profile and profile.is_grower)


class IsOwnerOrReadOnly(BasePermission):
    """Anyone allowed into the view may read an object, only its owner may change it.

    The owner is the first of these fields the object has: owner (gardens, care,
    marketplace), author (forum) or user (profile). For an object owned through
    another one, such as a journal entry and its garden, subclass and override
    get_owner_id.

    This is an object check, so a function view must call check_object_permissions.
    """

    message = 'Only the owner can change this.'
    owner_fields = ('owner', 'author', 'user')

    def get_owner_id(self, obj):
        for field in self.owner_fields:
            # The *_id column avoids loading the user row
            if hasattr(obj, f'{field}_id'):
                return getattr(obj, f'{field}_id')
        raise AttributeError(
            f'{type(obj).__name__} has none of {self.owner_fields}; override get_owner_id.'
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and self.get_owner_id(obj) == user.pk)


def check_object_permissions(request, obj):
    """Run the view's object checks (such as IsOwnerOrReadOnly) on obj.

    Class-based views do this inside get_object(). A function view has no self,
    so call this right after fetching the object. It raises the right 401 or 403.
    """
    request.parser_context['view'].check_object_permissions(request, obj)
