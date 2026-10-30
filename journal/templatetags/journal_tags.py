from django import template
from django.urls import reverse

from journal.models import PlantJournal

register = template.Library()


@register.simple_tag(takes_context=True)
def journal_for(context, planting):
    # What the gardens pages need from the journal: the entries this person may see,
    # the link to the plant's timeline, and the New Entry link for the owner
    user = context['request'].user
    is_owner = user == planting.garden.owner
    can_view = is_owner or PlantJournal.objects.filter(planting=planting, is_public=True).exists()
    return {
        'entries': planting.journal_entries.all() if can_view else [],
        'url': reverse('journal:plant_detail', args=[planting.pk]) + '?from=garden',
        'create_url': reverse('journal:create_plant_entry', args=[planting.pk]) if is_owner else '',
    }
