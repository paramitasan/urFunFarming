from django import template
from django.urls import reverse

from journal.models import PlantJournal

register = template.Library()


@register.simple_tag(takes_context=True)
def journal_for(context, planting):
    # What the gardens pages need from the journal: the entries this person may see,
    # the link to the plant's timeline, and the New Entry link for the owner
    user = context['request'].user
    is_owner = planting.garden.owner_id == user.pk
    # The garden pages add these two to their plantings, so a page of cards runs no extra queries
    is_public = getattr(planting, 'journal_is_public', None)
    if is_public is None:
        is_public = PlantJournal.objects.filter(planting=planting, is_public=True).exists()
    can_view = is_owner or is_public
    count = getattr(planting, 'journal_entry_count', None)
    return {
        # Only loaded if the template loops over it (the plant page does, the cards don't)
        'entries': planting.journal_entries.all() if can_view else [],
        'entry_count': (count if count is not None else planting.journal_entries.count()) if can_view else 0,
        'url': reverse('journal:plant_detail', args=[planting.pk]) + '?from=garden',
        'create_url': reverse('journal:create_plant_entry', args=[planting.pk]) if is_owner else '',
    }
