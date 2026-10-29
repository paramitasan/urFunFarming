from datetime import date, time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import Profile
from gardens.models import Garden, Planting
from journal.models import EntryPhoto, JournalEntry, PlantJournal

DEMO_PASSWORD = 'Seedling-Tray-42'
PHOTO = 'https://commons.wikimedia.org/wiki/Special:FilePath/{}?width=640'

# Each plant: garden, crop, planting date, public or not, and its entries
# Each entry: date, time, height in cm, stage, health, observation, photo file names
PLANTS = [
    ('Tebet Rooftop Garden', 'Cherry Tomato', date(2026, 9, 12), True, [
        (date(2026, 9, 12), time(7, 0), 8, 'seedling', 'healthy', 'First true leaves are out. Kept the strongest seedling and removed the rest.', []),
        (date(2026, 9, 22), time(17, 0), 34, 'vegetative', 'healthy', 'Moved from the seedling tray into the rooftop garden. Mixed compost into the planting hole and watered it in well.', []),
        (date(2026, 10, 6), time(6, 40), 61, 'vegetative', 'attention', 'Lower leaves turned yellow after the heavy rain. Removed them and added straw mulch so soil stops splashing onto the leaves.', []),
        (date(2026, 10, 18), time(7, 15), 85, 'flowering', 'healthy', 'Yellow flowers on the second truss. Tapped the stems in the morning to help with pollination.', []),
        (date(2026, 10, 24), time(7, 30), 92, 'fruiting', 'healthy', 'First 6 fruits set on the lower truss. Pinched off two suckers and tied the main stem to a bamboo stake.', ['Tomato_je.jpg', 'Tomatoes_plain_and_sliced.jpg']),
    ]),
    ('Tebet Rooftop Garden', "Bird's eye chili", date(2026, 9, 20), False, [
        (date(2026, 10, 10), time(17, 0), 30, 'vegetative', 'healthy', 'Bushy and dark green. Gave it a little fertilizer.', []),
        (date(2026, 10, 23), time(17, 10), 41, 'flowering', 'attention', 'Lots of buds opening. A few leaves curling at the edges, checked the undersides for mites but found none yet.', []),
    ]),
    ('Kitchen Balcony', 'Kangkung', date(2026, 10, 1), True, [
        (date(2026, 10, 22), time(6, 45), 28, 'harvested', 'healthy', 'Cut the first batch about 3 cm above the base so it can regrow. Watered right after.', []),
    ]),
    ('Kitchen Balcony', 'Thai basil', date(2026, 9, 25), True, [
        (date(2026, 10, 21), time(16, 20), 24, 'vegetative', 'healthy', 'Pinched the top to make it bushier. New side shoots are starting to show.', ['Ocimum_basilicum_8zz.jpg']),
    ]),
    ('Tebet Rooftop Garden', 'Pak choy', date(2026, 10, 10), False, [
        (date(2026, 10, 20), time(6, 30), 6, 'seedling', 'pest', 'Thinned to one seedling per hole. Two were eaten by snails overnight, set up a beer trap.', []),
    ]),
    ('Kitchen Balcony', 'Lettuce', date(2026, 10, 7), True, [
        (date(2026, 10, 14), time(6, 50), 4, 'seedling', 'healthy', 'Germination looks good, most of the seeds came up. Keeping the soil damp with a spray bottle.', []),
    ]),
    ('Tebet Rooftop Garden', 'Eggplant', date(2026, 9, 5), True, [
        (date(2026, 10, 12), time(8, 10), 48, 'flowering', 'healthy', 'First purple flowers opened. Added a handful of compost around the base.', []),
    ]),
    ('Kitchen Balcony', 'Mint', date(2026, 9, 15), True, [
        (date(2026, 10, 10), time(17, 45), 18, 'vegetative', 'healthy', 'Spreading fast in the pot. Trimmed the long stems and used them for tea.', []),
    ]),
    ('Tebet Rooftop Garden', 'Spring onion', date(2026, 9, 18), True, [
        (date(2026, 10, 8), time(6, 40), 26, 'vegetative', 'attention', 'Tips are turning a bit yellow. Cut back watering to every other day.', []),
    ]),
    ('Kitchen Balcony', 'Lemongrass', date(2026, 9, 28), True, [
        (date(2026, 10, 5), time(16, 30), 15, 'seedling', 'healthy', 'Planted three stalks from the market. New roots are showing at the bottom.', []),
    ]),
    ('Tebet Rooftop Garden', 'Spinach', date(2026, 9, 10), True, [
        (date(2026, 10, 2), time(7, 15), 22, 'harvested', 'healthy', 'Picked the outer leaves for dinner. Left the middle to keep growing.', []),
    ]),
    ('Kitchen Balcony', 'Strawberry', date(2026, 9, 1), True, [
        (date(2026, 9, 28), time(17, 20), 14, 'flowering', 'pest', 'Two white flowers opened. Found aphids under some leaves and sprayed soapy water.', []),
    ]),
]


class Command(BaseCommand):
    help = 'Adds demo users, gardens, plants and journal entries. Safe to run more than once.'

    def handle(self, *args, **options):
        grower = self.make_user('demo_grower', 'Sari', is_grower=True)
        self.make_user('demo_buyer', 'Dewi', is_buyer=True)

        new_entries = 0
        for garden_name, crop, planted, is_public, entries in PLANTS:
            # get_or_create looks for the row first and only makes it if it isn't there,
            # so running the command again doesn't add duplicates
            garden, _ = Garden.objects.get_or_create(
                owner=grower, name=garden_name,
                defaults={'location': 'Jakarta', 'growing_method': 'Containers', 'is_public': True},
            )
            planting, _ = Planting.objects.get_or_create(garden=garden, crop=crop, defaults={'planting_date': planted})
            PlantJournal.objects.get_or_create(planting=planting, defaults={'is_public': is_public})

            for day, at, height, stage, health, observation, photos in entries:
                entry, created = JournalEntry.objects.get_or_create(
                    planting=planting, date=day, time=at,
                    defaults={'height_cm': height, 'stage': stage, 'health': health, 'observation': observation},
                )
                if created:
                    new_entries += 1
                    for name in photos:
                        EntryPhoto.objects.create(entry=entry, url=PHOTO.format(name))

        self.stdout.write(self.style.SUCCESS(
            f'Demo journal ready ({new_entries} new entries). Log in as demo_grower or demo_buyer, password {DEMO_PASSWORD}'
        ))

    def make_user(self, username, display_name, is_grower=False, is_buyer=False):
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        Profile.objects.get_or_create(
            user=user, defaults={'display_name': display_name, 'is_grower': is_grower, 'is_buyer': is_buyer},
        )
        return user
