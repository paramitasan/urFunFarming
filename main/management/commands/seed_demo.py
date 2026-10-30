"""Fill the database with demo content so every page looks used.

Every demo account's username starts with demo_, and everything else this command makes
belongs to one of them, so --reset can remove it all without touching anyone else.
Each record is found by a stable key before it is made, so running it twice adds nothing new.
"""
import random
from collections import Counter
from datetime import time, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.locations import find_village
from accounts.models import Profile

PREFIX = 'demo_'
SEED = 2026

# username, display name, grower, buyer, BMKG village code (adm4), bio
USERS = [
    ('demo_ayu', 'Ayu Lestari', True, False, '31.74.01.1001',
     'Rooftop grower in Tebet. Pak choy and selada in grow bags, plus one stubborn tomat ceri.'),
    ('demo_bima', 'Bima Prasetyo', True, False, '32.76.06.1002',
     'Student in Kukusan growing kangkung and cabai rawit on a small NFT rack behind the kos.'),
    ('demo_rina', 'Rina Wulandari', True, False, '31.75.02.1005',
     'Balcony herbs in Rawamangun: basil, mint and serai. Happy to swap cuttings with neighbours.'),
    ('demo_dimas', 'Dimas Saputra', True, False, '32.76.01.1008',
     'Backyard beds and a wick hydroponic shelf in Pancoran Mas. Learning tomat ceri the hard way.'),
    ('demo_nadia', 'Nadia Putri', True, True, '32.76.06.1001',
     'Terrace greens in Beji. I sell my extra selada and buy the herbs I cannot keep alive.'),
    ('demo_yoga', 'Yoga Pratama', True, True, '31.74.09.1004',
     'Community garden volunteer near Lenteng Agung station. Mostly cabai and kangkung.'),
    ('demo_sekar', 'Sekar Ayuningtyas', False, True, '31.74.01.1003',
     'Home cook in Menteng Dalam who likes knowing who grew the vegetables.'),
    ('demo_fajar', 'Fajar Nugroho', False, True, '32.76.06.1005',
     'Runs a small warung near campus in Pondok Cina and buys fresh herbs and greens every week.'),
]

# owner: [(garden name, location, growing method, public, public summary, private notes,
#          [(planting name, crop, optional growing method), ...])]
# Planting names are unique across the demo, so later parts can refer to a planting by name.
GARDENS = {
    'demo_ayu': [
        ('Rooftop Grow Bags', 'Tebet, Jakarta Selatan', 'Grow bags', True,
         'Twelve grow bags on the roof of our rumah susun, full sun from 9 to 3.',
         'Roof door key is with Pak RT. Water is off from 10:00 to 14:00.',
         [('Rooftop pak choy', 'Pak choy'), ('Rooftop selada keriting', 'Selada'),
          ('Tomat ceri by the water tank', 'Tomat ceri'), ('Rooftop cabai rawit', 'Cabai rawit')]),
        ('Kitchen Window Herbs', 'Tebet, Jakarta Selatan', 'Pots', False,
         'Two pots on the kitchen window ledge.',
         'Window only gets sun until 11. Turn the pots every few days.',
         [('Kitchen basil', 'Basil'), ('Kitchen mint', 'Mint')]),
        ('Stairwell Seed Trays', 'Tebet, Jakarta Selatan', 'Recycled trays', True,
         'Old egg trays and takeaway boxes on the stairwell railing, shared with the neighbours.',
         'Ask Bu Ani before moving her trays.',
         [('Stairwell kangkung', 'Kangkung'), ('Stairwell pak choy', 'Pak choy'), ('Stairwell selada', 'Selada')]),
    ],
    'demo_bima': [
        ('Kos NFT Rack', 'Beji, Depok', 'NFT hydroponics', True,
         'A four-pipe NFT rack behind the kos, built from PVC and a fish tank pump.',
         'Pump is on the timer by the laundry tap. AB mix is under the sink.',
         [('NFT kangkung', 'Kangkung'), ('NFT pak choy', 'Pak choy'), ('NFT selada', 'Selada'),
          ('NFT basil', 'Basil'), ('Mint cuttings in a jar', 'Mint', 'Water propagation')]),
        ('Cabai Corner', 'Beji, Depok', 'Polybags', False,
         'Polybags along the back fence.',
         'Landlord asked to keep the path clear. Neem oil is in the blue bottle.',
         [('Cabai rawit hijau', 'Cabai rawit'), ('Cabai rawit merah', 'Cabai rawit'),
          ('Polybag tomat ceri', 'Tomat ceri')]),
    ],
    'demo_rina': [
        ('Rawamangun Balcony Herbs', 'Pulogadung, Jakarta Timur', 'Containers', True,
         'A sunny third-floor balcony packed with herbs for cooking and tea.',
         'Neighbour below complained about drips, so water before 7.',
         [('Balcony basil', 'Basil'), ('Thai basil (kemangi)', 'Basil'), ('Balcony mint', 'Mint'),
          ('Balcony selada', 'Selada')]),
        ('Laundry Line Planters', 'Pulogadung, Jakarta Timur', 'Hanging planters', False,
         'Hanging planters on the old laundry line.',
         'Hooks on the left side are loose. Do not hang anything heavier than 3 kg.',
         [('Hanging kangkung', 'Kangkung'), ('Hanging mint', 'Mint')]),
        ('Front Gate Pots', 'Pulogadung, Jakarta Timur', 'Pots', True,
         'Big pots by the front gate that everyone on the gang walks past.',
         'Kids pick the tomatoes, which is fine. Keep the cabai out of reach.',
         [('Gate cabai rawit', 'Cabai rawit'), ('Gate tomat ceri', 'Tomat ceri'), ('Gate basil', 'Basil')]),
    ],
    'demo_dimas': [
        ('Backyard Raised Beds', 'Pancoran Mas, Depok', 'Raised beds', True,
         'Three raised beds made from old pallets, filled with compost from the RW bank sampah.',
         'Bed 3 drains badly after heavy rain. Compost bin is behind the shed.',
         [('Raised bed tomat ceri', 'Tomat ceri'), ('Raised bed cabai rawit', 'Cabai rawit'),
          ('Raised bed pak choy', 'Pak choy'), ('Raised bed kangkung', 'Kangkung'), ('Raised bed selada', 'Selada')]),
        ('Wick Hydroponic Shelf', 'Pancoran Mas, Depok', 'Wick hydroponics', True,
         'A three-level shelf of wick pots under the carport roof.',
         'Top up the reservoirs every Monday and Thursday.',
         [('Wick selada', 'Selada'), ('Wick pak choy', 'Pak choy'), ('Wick basil', 'Basil')]),
        ('Seedling Nursery', 'Pancoran Mas, Depok', 'Seedling trays', False,
         'Seedling trays on a shelf by the kitchen door.',
         'Keep the shade net on until the seedlings have four leaves.',
         [('Nursery tomat ceri', 'Tomat ceri'), ('Nursery cabai rawit', 'Cabai rawit')]),
    ],
    'demo_nadia': [
        ('Beji Terrace Greens', 'Beji, Depok', 'Containers', True,
         'Long planter boxes along the terrace railing, mostly leafy greens.',
         'The tap on the terrace leaks, close it tight.',
         [('Terrace selada', 'Selada'), ('Terrace pak choy', 'Pak choy'), ('Terrace kangkung', 'Kangkung')]),
        ('Bedroom Window Sill', 'Beji, Depok', 'Pots', False,
         'Two small pots on the bedroom window sill.',
         'Only morning sun here. Mint likes it, basil not so much.',
         [('Window mint', 'Mint'), ('Window basil', 'Basil')]),
    ],
    'demo_yoga': [
        ('Lenteng Agung Community Plot', 'Jagakarsa, Jakarta Selatan', 'In-ground beds', True,
         'A shared plot near Lenteng Agung station, tended by volunteers every Saturday morning.',
         'Tool shed code is 2306. Log what you take in the book.',
         [('Community cabai rawit', 'Cabai rawit'), ('Community kangkung', 'Kangkung'),
          ('Community tomat ceri', 'Tomat ceri'), ('Community pak choy', 'Pak choy')]),
        ('Station Fence Planters', 'Jagakarsa, Jakarta Selatan', 'Vertical planters', True,
         'Vertical planters made from paint buckets, hung on the fence by the station path.',
         'Two planters were knocked down last month. Check the wire ties.',
         [('Vertical selada', 'Selada'), ('Vertical mint', 'Mint'), ('Vertical basil', 'Basil')]),
        ('Home Dutch Bucket', 'Jagakarsa, Jakarta Selatan', 'Dutch bucket hydroponics', False,
         'Two dutch buckets in the side yard.',
         'Pump fuse blew once. Spare fuse is taped under the reservoir lid.',
         [('Dutch bucket tomat ceri', 'Tomat ceri'), ('Dutch bucket cabai rawit', 'Cabai rawit')]),
    ],
}
SLOW_CROPS = {'Tomat ceri', 'Cabai rawit'}

# crop: (note group, height in cm when grown, [(days after planting, stage it reaches), ...])
CROPS = {
    'Pak choy': ('leafy', 25, [(0, 'seedling'), (10, 'vegetative'), (35, 'harvested')]),
    'Selada': ('leafy', 22, [(0, 'seedling'), (12, 'vegetative'), (40, 'harvested')]),
    'Kangkung': ('leafy', 35, [(0, 'seedling'), (7, 'vegetative'), (25, 'harvested')]),
    'Basil': ('herb', 45, [(0, 'seedling'), (12, 'vegetative'), (45, 'flowering')]),
    'Mint': ('herb', 30, [(0, 'seedling'), (10, 'vegetative'), (35, 'harvested')]),
    'Cabai rawit': ('fruit', 60, [(0, 'seedling'), (14, 'vegetative'), (38, 'flowering'), (48, 'fruiting'), (58, 'harvested')]),
    'Tomat ceri': ('fruit', 110, [(0, 'seedling'), (12, 'vegetative'), (30, 'flowering'), (40, 'fruiting'), (54, 'harvested')]),
}

# Plantings left without entries, so the journal's empty state shows too
NO_JOURNAL = {
    'Kitchen mint', 'Stairwell selada', 'Cabai rawit merah', 'Hanging mint',
    'Nursery cabai rawit', 'Window basil', 'Dutch bucket cabai rawit',
}

FIRST_NOTES = [
    'Planted the {plant} today and watered it in well.',
    'Sowed the {plant} today. Covered the seeds lightly and misted until damp.',
    'Transplanted the {plant} seedlings today and shaded them with a net for a few days.',
]

NOTES = {
    ('leafy', 'seedling'): [
        'First true leaves are out on the {plant}.',
        'Thinned the {plant} to one seedling per hole and kept the strongest.',
        'Seedlings look a bit leggy, moved them to a spot with more morning sun.',
        'Misted the {plant} twice today, the top layer dries out fast in this heat.',
    ],
    ('leafy', 'vegetative'): [
        'Leaves filling out nicely. Watering every morning before 7.',
        'Gave the {plant} a half dose of liquid fertilizer.',
        "Growing fast after this week's rain. New leaves almost every day.",
        'Loosened the soil around the base and topped up with compost.',
        'Leaves are deep green and about hand-sized now.',
    ],
    ('leafy', 'harvested'): [
        'Harvested the first {plant} today, enough for dinner.',
        'Cut the outer leaves and left the centre to keep growing.',
        'Picked another batch of {plant} and shared some with the neighbours.',
        'Still picking a few leaves every couple of days.',
        'Harvest done. Cleared the spot and added compost for the next round.',
    ],
    ('herb', 'seedling'): [
        'New leaves coming in, the {plant} has settled in well. Keeping it in light shade.',
        'First pair of true leaves on the {plant}.',
        'Moved the {plant} to a bigger pot, the roots were circling the bottom.',
        'Watering lightly every evening, the soil stays damp until morning.',
    ],
    ('herb', 'vegetative'): [
        'Pinched the top of the {plant} so it grows bushier.',
        "New side shoots coming out after last week's pinching.",
        'Picked a few leaves for cooking. It smells amazing.',
        'Turned the pot so the {plant} stops leaning toward the light.',
        'Fed it with diluted rice water once this week.',
    ],
    ('herb', 'flowering'): [
        'Flower spikes appearing on the {plant}. Pinched them off to keep the leaves coming.',
        'Left one flower spike for the bees and pinched the rest.',
        'Lots of buds this week. Harvested the tops before they open.',
    ],
    ('herb', 'harvested'): [
        'Cut a big handful of {plant} for tea. It bounced back within days.',
        'Trimmed the long stems and hung them to dry.',
        'Harvested about a third of the {plant} and gave some to the warung next door.',
    ],
    ('fruit', 'seedling'): [
        'Seedlings have their first true leaves.',
        'Kept the strongest {plant} seedling and removed the rest.',
        'Hardening off the seedlings in the morning sun for an hour a day.',
        'Still small but the stem is getting thicker.',
    ],
    ('fruit', 'vegetative'): [
        'Tied the {plant} loosely to a bamboo stake.',
        'Pinched off the small shoots below the first branch.',
        'Added a handful of compost around the base and watered it in.',
        'Bushy and dark green. Gave it a little NPK.',
        'Removed the lowest leaves so soil does not splash onto them.',
    ],
    ('fruit', 'flowering'): [
        'First flower buds on the {plant}.',
        'Flowers opening. Tapped the stems in the morning to help pollination.',
        'More flowers this week, a few dropped after the heavy rain.',
    ],
    ('fruit', 'fruiting'): [
        'First small green fruits have set on the {plant}.',
        'Counted a dozen fruits on the {plant}. Switched to a potassium-rich fertilizer.',
        'Fruits getting bigger. Added another stake because the branches are bending.',
    ],
    ('fruit', 'harvested'): [
        'Picked the first ripe {plant} today!',
        'Harvested a small bowl of {plant}. More are turning colour.',
        'Second picking, enough to share with the neighbours.',
    ],
}

# Added after the stage note when the plant is not healthy
HEALTH_NOTES = {
    'attention': [
        'A few lower leaves turned yellow, removed them.',
        'Leaves drooping in the afternoon heat, added straw mulch.',
        'Some leaf tips look burnt, cutting back the fertilizer.',
        'Soil stayed soggy after the rain, holding off on watering.',
    ],
    'pest': [
        'Found aphids under some leaves and sprayed soapy water.',
        'Snails ate two leaves overnight, set up a beer trap.',
        'Spotted whiteflies, sprayed diluted neem oil in the evening.',
        'Caterpillar holes on a few leaves, picked them off by hand.',
    ],
}

# activity: [(title, private notes), ...]; check_ph only goes to hydroponic plantings
CARE_TASKS = {
    'water': [('Water the {plant}', 'Water early, before the sun gets strong.'),
              ('Deep watering for the {plant}', 'Soak until it drains from the bottom.')],
    'fertilize': [('Feed the {plant} with liquid fertilizer', 'POC from the bank sampah, 5 ml per litre.'),
                  ('Add compost around the {plant}', 'One handful per plant, keep it off the stem.')],
    'prune': [('Prune the {plant}', 'Take off yellow leaves and anything touching the soil.')],
    'check_ph': [('Check the pH for the {plant}', 'Target 5.8 to 6.5. pH down is in the red bottle.')],
    'harvest': [('Harvest the {plant}', 'Bring scissors and the basket. Morning is best.')],
    'other': [('Check the {plant} for pests', 'Look under the leaves after the rain.'),
              ('Mulch around the {plant}', 'Use the dry leaves from the yard.')],
}
# Five tasks per grower; completed ones are in the past, to-dos in the coming week
TASK_STATUSES = [('completed', -10, -1), ('completed', -10, -1), ('in_progress', -1, 0), ('todo', 0, 3), ('todo', 1, 7)]

# title, category, unit, (fewest, most) in stock, price in rupiah, per how many units, description
# A price of 0 is shown as free
PRODUCTS = [
    ('Fresh pak choy', 'vegetables', 'bunch', (4, 12), 7000, 1,
     'Pak choy picked the morning you collect, about 250 g per bunch. Grown without pesticides.'),
    ('Baby pak choy pack', 'vegetables', 'pack', (3, 8), 12000, 1,
     'Young pak choy heads, 300 g per pack. Good for stir-fry or soup.'),
    ('Kangkung bunches', 'vegetables', 'bunch', (5, 15), 5000, 1,
     'Tender kangkung cut this morning. Perfect for cah kangkung or plecing.'),
    ('Hydroponic kangkung', 'vegetables', 'g', (500, 2000), 6000, 250,
     'Clean hydroponic kangkung with no soil on the roots, sold by weight.'),
    ('Selada keriting', 'vegetables', 'head', (4, 10), 6000, 1,
     'Crisp curly lettuce from our planters, about 150 g per head.'),
    ('Hydroponic selada', 'vegetables', 'pack', (3, 8), 15000, 1,
     'Green and red lettuce, 250 g per pack, roots left on so it stays fresh longer.'),
    ('Cabai rawit merah', 'vegetables', 'g', (200, 800), 8000, 100,
     "Very spicy bird's eye chili, picked ripe and red."),
    ('Cabai rawit hijau', 'vegetables', 'g', (200, 600), 6000, 100,
     'Green cabai rawit for sambal and pickles, picked this week.'),
    ('Tomat ceri', 'fruits', 'g', (500, 2000), 12000, 250,
     'Sweet cherry tomatoes, mixed red and orange. Picked when fully ripe.'),
    ('Tomat ceri snack box', 'fruits', 'pack', (2, 6), 15000, 1,
     'A 300 g box of cherry tomatoes, washed and ready to eat.'),
    ('Sweet basil', 'herbs', 'bunch', (3, 8), 5000, 1,
     'Fragrant Genovese basil, about 50 g per bunch. Great for pesto.'),
    ('Kemangi (Thai basil)', 'herbs', 'bunch', (4, 10), 3000, 1,
     'Kemangi for lalapan and pepes, picked fresh on the day.'),
    ('Fresh mint', 'herbs', 'bunch', (3, 8), 4000, 1,
     'Spearmint for tea, drinks or salad, about 40 g per bunch.'),
    ('Free mint cuttings', 'herbs', 'piece', (5, 15), 0, 1,
     'Rooted mint cuttings to start your own pot. Free, just bring a small container.'),
    ('Free basil seedlings', 'herbs', 'piece', (4, 10), 0, 1,
     'Extra basil seedlings from my tray, about 5 cm tall. Free to a good home.'),
    ('Kangkung cuttings for regrowing', 'vegetables', 'bunch', (2, 6), 0, 1,
     'Stems with roots that regrow in water or soil. Free for neighbours.'),
    ('Cabai rawit seedlings', 'vegetables', 'piece', (4, 12), 2500, 1,
     'Healthy chili seedlings in small polybags, ready to transplant.'),
    ('Mixed salad greens', 'vegetables', 'pack', (3, 8), 18000, 1,
     'Selada, pak choy and basil in one 400 g pack. Enough for a family salad.'),
    ('Extra pak choy, free', 'vegetables', 'bunch', (2, 5), 0, 1,
     'Harvested too much this week. Free, first come first served.'),
    ('Mint and basil bundle', 'herbs', 'pack', (2, 6), 10000, 1,
     'One bunch of mint and one bunch of basil together.'),
]
LISTINGS_PER_GROWER = 9

# author, topic, days ago, marked answered, title, question, [answers from other demo users]
FORUM = [
    ('demo_sekar', 'plant_care', 18, True, 'Why are my pak choy leaves full of tiny holes?',
     'I bought a pak choy seedling at the market two weeks ago and planted it in a pot on my terrace. '
     'Now the leaves are full of tiny round holes, but I never see any bugs during the day. '
     'Is it still safe to eat, and how do I stop it?',
     ['Tiny round holes with no visible bugs is usually flea beetles or caterpillars that feed at night. '
      'Go out with a torch around 8 pm and check under the leaves.',
      'It is safe to eat, just wash it well. I cover my pak choy with a cheap insect net and the holes stopped completely.',
      'Could also be snails if the holes are bigger and there is a shiny trail. A saucer of beer next to the pot works for me.',
      'Following this, the same thing happened to my selada last month.']),
    ('demo_bima', 'hydroponics', 25, True, 'What EC should I run for kangkung in NFT?',
     'My NFT rack has kangkung, pak choy and selada sharing one reservoir. I am running AB mix at about EC 1.4 '
     'but the kangkung looks pale while the selada is fine. Should I raise it, or split the crops into separate pipes?',
     ['Kangkung is happy anywhere from 1.2 to 1.8. Pale leaves are more often a pH problem, so check that first.',
      'Sharing one reservoir is normal for leafy greens. I run 1.6 for mixed greens and top up with plain water when it is hot.',
      'Check the water temperature too. If the reservoir sits in the sun it can pass 30 °C in the afternoon '
      'and the roots stop taking up nutrients.',
      'I wrap my reservoir in an old rice sack and keep it shaded, the difference was big.',
      'Same thing happened to me and my pH was above 7. Bringing it down to 6.2 fixed it within a week.']),
    ('demo_rina', 'balcony', 15, False, 'Basil keeps flowering on my west-facing balcony',
     'My basil gets strong afternoon sun from about 1 pm until sunset. It keeps trying to flower even though '
     'I pinch the tops every few days, and the leaves are getting smaller. Is it the heat, or am I doing something wrong?',
     ['Afternoon sun in Jakarta is brutal for basil. A piece of shade net from 1 to 3 pm helps a lot.',
      'Pinch just above a pair of leaves, not only the flower tip, and harvest more often.',
      'Kemangi handles the heat better than Genovese in my experience. Maybe try both side by side.']),
    ('demo_fajar', 'other', 21, True, 'Where can I buy good seeds around Depok?',
     'I run a small warung near campus and want to start growing some of my own herbs. '
     'Is there a shop in Depok that sells good seeds, or is online the only option?',
     ['There is a farm supply shop near Pasar Depok Lama that sells local seed brands, plus polybags and cocopeat.',
      'I buy online from local seed sellers, but check the packing date. Old seeds germinate badly.',
      'You can also ask growers here. I have extra basil and kemangi seeds and can drop some off at the warung.',
      'The city agriculture office sometimes hands out free seeds at Car Free Day on Sunday mornings.']),
    ('demo_dimas', 'plant_care', 12, True, 'Tomat ceri leaves curling and turning yellow from the bottom',
     'My cherry tomatoes in the raised bed are about knee high and just starting to flower. The lowest leaves '
     'are curling and turning yellow, and it is slowly moving upward. We had a lot of rain last week. '
     'Is this a disease or just the weather?',
     ['Yellowing from the bottom after heavy rain is often early blight or waterlogged roots. Look for brown rings on the leaves.',
      'Remove the yellow leaves and throw them away, not in the compost. Mulch with straw so soil does not splash up.',
      'If the bed drains badly, poke some deep holes with a bamboo stick to let the water out.',
      'Mine did the same and it was a magnesium deficiency. A spoon of Epsom salt in a watering can fixed it.',
      'Water only at the base, never the leaves, and preferably in the morning.',
      'I had this on my rooftop. Spraying diluted baking soda once a week slowed it down a lot.']),
    ('demo_ayu', 'weather', 9, True, 'How do you protect rooftop plants from heavy afternoon rain?',
     'Our rooftop in Tebet gets sudden storms around 3 pm almost every day now. The rain flattens my selada '
     'and splashes soil everywhere. What do you use to cover the plants without blocking all the sun?',
     ['A clear UV plastic roof on a simple bamboo frame works well. It still lets the light through.',
      'I check the forecast in the morning and move the pots under the stairs when rain is likely.',
      'Shade net at 50 percent breaks up the heavy drops and also helps in the midday heat.',
      'Raise the grow bags off the floor so they do not sit in standing water after the storm.',
      'Mulch on top of the soil stops most of the splashing.']),
    ('demo_nadia', 'seedlings', 16, False, 'Selada seeds will not germinate in this heat',
     'I sowed lettuce seeds three times this month and fewer than a third came up. The trays are on my terrace '
     'and get warm during the day. Do lettuce seeds need cooler temperatures?',
     ['Yes, lettuce germinates badly above about 28 °C. Sow in the evening and keep the tray indoors for the first two days.',
      'Do not bury lettuce seeds, they need light to germinate. Just press them onto the surface.',
      'Soak the seeds for a few hours, then keep them in a damp tissue in the fridge overnight before sowing.',
      'I use rockwool and keep it in the shade under the stairs. Germination went from half to almost all.']),
    ('demo_yoga', 'aeroponics', 11, False, 'Has anyone tried a DIY aeroponic tower with a pond pump?',
     'I want to build a small aeroponic tower for the community plot using a 20 litre bucket and a cheap pond pump. '
     'Is a normal pump strong enough for misting, or do I need a high-pressure one?',
     ['A pond pump will not make a real mist, it is more of a spray. That is still fine for a low-pressure tower, '
      'it is how most DIY ones work.',
      'Use a timer, 1 minute on and 5 minutes off. The roots dry out very fast if the pump stops, so watch out for power cuts.']),
    ('demo_sekar', 'balcony', 7, True, 'Easiest herbs for a beginner with only morning sun?',
     'I have a small balcony that only gets sun until about 11. I mostly cook Indonesian food. '
     'Which herbs would actually survive and be useful in the kitchen?',
     ['Mint is almost impossible to kill and loves morning sun. Keep it in its own pot.',
      'Kemangi, daun bawang and seledri all do fine with half a day of sun.',
      'Serai wants more sun but still grows slowly in your conditions. Start from market stalks with the base intact.',
      'I would skip cabai, it needs full sun to fruit well.',
      'Pandan in a big pot also works in partial shade and smells great in rice.']),
    ('demo_bima', 'weather', 5, False, 'Is it worth watering when the forecast says rain in the afternoon?',
     'Most days the forecast says rain after 2 pm, but sometimes it never comes. '
     'Do you still water in the morning, or wait and risk it?',
     ['I always water in the morning anyway. Plants in pots dry out by noon even if it rains later.',
      'For in-ground beds I skip it if the soil is still damp a finger deep.',
      'The Plant care page shows the hourly forecast. I only skip watering when it says more than 5 mm of rain.']),
    ('demo_rina', 'plant_care', 20, True, 'Mint taking over the whole planter, how do I control it?',
     'I planted mint in a long planter together with basil and selada. Two months later the mint has runners '
     'everywhere and is choking the others. How do I keep it in check?',
     ['Mint should always get its own pot. Dig it out and replant it in a separate container.',
      'If you want it in the planter, sink a bottomless pot or a cut bucket into the soil to hold the roots in.',
      'Cut it back hard every couple of weeks and use it for tea. It grows back very quickly.']),
    ('demo_dimas', 'hydroponics', 8, False, 'Algae growing in my wick system reservoir',
     'The reservoirs of my wick pots have turned green and slimy. The plants still look okay. '
     'Is the algae harmful, and how do I stop it coming back?',
     ['Algae grows wherever light reaches the nutrient water. Cover the reservoirs or paint them black.',
      'It competes for nutrients and oxygen, so clean it out. I scrub mine with diluted hydrogen peroxide '
      'whenever I change the solution.']),
    ('demo_fajar', 'other', 3, False, 'How long do kangkung bunches stay fresh after harvest?',
     'I buy kangkung from growers nearby for the warung. It wilts within a day in the heat. '
     'Any tips to keep it fresh longer?',
     ['Stand the stems in a bucket of water like flowers and keep it in the shade. It stays crisp for two days that way.']),
    ('demo_yoga', 'seedlings', 1, False, 'When should I move cabai seedlings from the tray to polybags?',
     'My cabai rawit seedlings are about three weeks old with four true leaves. '
     'Is that the right time to transplant, or should I wait until they are bigger?', []),
    ('demo_nadia', 'aeroponics', 0, False, 'What mist timer settings work for a small aeroponic box?',
     'I am setting up a small aeroponic box for selada. How long should the misting cycle be in our hot weather, '
     'and should it run at night too?', []),
]


class Command(BaseCommand):
    help = 'Create demo users, gardens, journals, care tasks, listings and forum posts. Safe to run more than once.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete every demo_ account and what it owns, then seed again.')
        parser.add_argument('--force', action='store_true', help='Allow running while DEBUG is off, e.g. on PWS.')

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise CommandError('DEBUG is off, so this looks like a live site. Add --force if you really want demo data here.')

        self.today = timezone.localdate()
        self.created = Counter()
        self.existing = Counter()
        self.skipped = []
        self.removed = 0

        # All or nothing: if one part fails, the database is left as it was
        with transaction.atomic():
            if options['reset']:
                self.reset()
            self.seed_users()
            self.seed_gardens()
            self.seed_journals()
            self.seed_care_tasks()
            self.seed_listings()
            self.seed_forum()

        self.print_summary()

    def rng(self, *key):
        # Each record gets its own generator from the fixed seed, so its values are the same
        # on every run and never depend on what else already exists
        return random.Random(':'.join(str(part) for part in (SEED, *key)))

    def model(self, app_label, model_name, part):
        # A missing app or model skips its part, so the command still runs while a module is unfinished
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            self.skipped.append(f'{part} ({app_label}.{model_name} does not exist yet)')
            return None

    def tally(self, label, created):
        (self.created if created else self.existing)[label] += 1

    def reset(self):
        # On SQLite startswith ignores case, so check the exact prefix again in Python.
        # Gardens, journals, tasks, listings and forum posts all belong to a user,
        # so deleting the demo users removes everything they own and nothing else.
        demo_ids = [
            user.pk for user in User.objects.filter(username__startswith=PREFIX)
            if user.username.startswith(PREFIX)
        ]
        self.removed = len(demo_ids)
        User.objects.filter(pk__in=demo_ids).delete()

    def seed_users(self):
        password = settings.DEMO_PASSWORD
        self.users = {}
        for username, display_name, is_grower, is_buyer, code, bio in USERS:
            email = f'{username}@example.invalid'
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            if not created and user.email != email:
                raise CommandError(f'{username} already belongs to a real account, so no demo data was changed.')
            # Only rehash when the password setting changed, so reruns stay quick
            if created or not user.check_password(password):
                user.set_password(password)
                user.save()
            self.tally('users', created)

            # Area and city come from the village code, the same way the profile form fills them
            place = find_village(code)
            _, created = Profile.objects.get_or_create(user=user, defaults={
                'display_name': display_name, 'is_grower': is_grower, 'is_buyer': is_buyer, 'bio': bio,
                'adm4_code': code, 'area': place['district'], 'city': place['city'], 'contact_email': email,
            })
            self.tally('profiles', created)
            self.users[username] = user

        self.growers = [self.users[row[0]] for row in USERS if row[2]]

    def seed_gardens(self):
        self.plantings = {}
        Garden = self.model('gardens', 'Garden', 'gardens and plantings')
        if not Garden:
            return
        Planting = self.model('gardens', 'Planting', 'plantings')

        for username, gardens in GARDENS.items():
            for name, location, method, is_public, summary, notes, plants in gardens:
                garden, created = Garden.objects.get_or_create(owner=self.users[username], name=name, defaults={
                    'location': location, 'growing_method': method, 'is_public': is_public,
                    'public_summary': summary, 'private_notes': notes,
                })
                self.tally('gardens', created)
                if not Planting:
                    continue

                for plant_name, crop, *plant_method in plants:
                    # Planted some time in the past two months; fruit crops grow slowly, so they went in earlier
                    earliest = 25 if crop in SLOW_CROPS else 2
                    planted = self.today - timedelta(days=self.rng('planting', plant_name).randint(earliest, 60))
                    planting, created = Planting.objects.get_or_create(garden=garden, name=plant_name, defaults={
                        'crop': crop, 'planting_date': planted, 'growing_method': plant_method[0] if plant_method else '',
                    })
                    self.tally('plantings', created)
                    self.plantings[plant_name] = planting

    def seed_journals(self):
        Entry = self.model('journal', 'JournalEntry', 'journal entries')
        if not Entry:
            return
        Journal = self.model('journal', 'PlantJournal', 'journal visibility')

        for name, planting in self.plantings.items():
            if name in NO_JOURNAL:
                continue
            if Journal:
                # Most journals in a public garden are public too; a private garden keeps them private
                is_public = planting.garden.is_public and self.rng('journal-visibility', name).random() < 0.8
                _, created = Journal.objects.get_or_create(planting=planting, defaults={'is_public': is_public})
                self.tally('plant journals', created)

            # A planting that already has entries keeps them, so a rerun on a later day adds nothing
            existing = planting.journal_entries.count()
            if existing:
                self.existing['journal entries'] += existing
                continue
            for entry in self.journal_plan(planting):
                Entry.objects.create(planting=planting, **entry)
                self.created['journal entries'] += 1

    def journal_plan(self, planting):
        """3 to 10 entries from planting day to today, each with a note that fits its stage."""
        rng = self.rng('journal', planting.name)
        group, full_height, stages = CROPS.get(planting.crop, CROPS['Selada'])
        plant = planting.crop.lower()
        age = (self.today - planting.planting_date).days
        if age < 2:
            # Too new for three dated entries, e.g. after someone edited the planting date
            return
        count = min(rng.randint(3, 10), age + 1)
        used = set()
        height = 0

        for i in range(count):
            # Spread evenly; steps of at least one day keep every date apart
            day = round(i * age / (count - 1))
            stage = [name for start, name in stages if start <= day][-1]
            # Growth speeds up after the seedling weeks instead of rising in a straight line
            grown = 2 + (full_height - 2) * min(day / stages[-1][0], 1) ** 1.5 * rng.uniform(0.9, 1.05)
            height = max(height, round(grown, 1))

            pool =FIRST_NOTES if i == 0 else NOTES[group, stage]
            unused = [n for n in pool if n not in used]
            if not unused:
                # More entries than notes: repeat one from the middle, never "first" or "done"
                note = rng.choice(pool[1:-1] or pool)
            elif i == 0 or stage == 'vegetative':
                note = rng.choice(unused)
            else:
                # Stage notes are written in order, e.g. the first harvest before the last
                note = unused[0]
            used.add(note)
            roll = rng.random()
            health = 'pest' if roll < 0.08 else 'attention' if roll < 0.22 else 'healthy'
            observation = note.format(plant=plant)
            if health != 'healthy':
                observation += ' ' + rng.choice(HEALTH_NOTES[health])

            # Today's entry is always from this morning, never later than now
            hour = rng.choice([6, 7]) if day == age else rng.choice([6, 7, 16, 17])
            yield {
                'date': planting.planting_date + timedelta(days=day), 'time': time(hour, rng.choice([0, 15, 30, 45])),
                'height_cm': Decimal(str(height)), 'stage': stage, 'health': health, 'observation': observation,
            }

    def seed_care_tasks(self):
        Task = self.model('care', 'CareTask', 'care tasks')
        if not Task or not self.plantings:
            return

        for username, gardens in GARDENS.items():
            owner = self.users[username]
            names = [plant[0] for garden in gardens for plant in garden[6]]
            rng = self.rng('care', username)
            # Five different plantings, all the grower's own
            for name, (status, earliest, latest) in zip(rng.sample(names, len(TASK_STATUSES)), TASK_STATUSES):
                planting = self.plantings[name]
                activities = [a for a in CARE_TASKS if a != 'check_ph' or 'hydroponics' in planting.method.lower()]
                activity = rng.choice(activities)
                title, notes = rng.choice(CARE_TASKS[activity])
                _, created = Task.objects.get_or_create(
                    owner=owner, planting=planting, title=title.format(plant=planting.crop.lower()), defaults={
                        'activity': activity, 'status': status, 'notes': notes,
                        'target_date': self.today + timedelta(days=rng.randint(earliest, latest)),
                        'target_time': rng.choice([None, time(6, 30), time(7, 0), time(16, 30), time(17, 0)]),
                    },
                )
                self.tally('care tasks', created)

    def seed_listings(self):
        Listing = self.model('marketplace', 'HarvestListing', 'market listings')
        if not Listing:
            return

        for user in self.growers:
            profile = user.profile
            rng = self.rng('listings', user.username)
            for slot, index in enumerate(rng.sample(range(len(PRODUCTS)), LISTINGS_PER_GROWER)):
                title, category, unit, (fewest, most), price, per, description = PRODUCTS[index]
                quantity = rng.randrange(fewest, most + 1, 100 if unit == 'g' else 1)
                # Each grower prices a little differently, rounded to Rp500
                price = round(price * rng.choice([0.8, 0.9, 1, 1.1, 1.25]) / 500) * 500

                # Most are on offer now, a few start in the next days; some have no end date
                if rng.random() < 0.15:
                    available_from = self.today + timedelta(days=rng.randint(1, 5))
                else:
                    available_from = self.today - timedelta(days=rng.randint(0, 10))
                until = None if rng.random() < 0.3 else max(available_from, self.today) + timedelta(days=rng.randint(3, 14))

                # The same id for the same grower and slot on every run
                pk = uuid5(NAMESPACE_URL, f'urfunfarming/seed_demo/{user.username}/{slot}')
                _, created = Listing.objects.get_or_create(pk=pk, defaults={
                    'owner': user, 'title': title, 'category': category, 'unit': unit,
                    'quantity': Decimal(quantity), 'price': Decimal(price), 'price_quantity': Decimal(per),
                    'description': f'{description} Collect in {profile.area}.',
                    'area': profile.area, 'city': 'Depok' if profile.city == 'Depok' else 'Jakarta',
                    'available_from': available_from, 'available_until': until,
                    'is_available': rng.random() >= 0.07, 'is_demo': True,
                })
                self.tally('market listings', created)

    def seed_forum(self):
        Question = self.model('forum', 'Forum', 'forum questions')
        if not Question:
            return
        Answer = self.model('forum', 'Reply', 'forum answers')
        now = timezone.now()
        usernames = [row[0] for row in USERS]

        for username, topic, days_ago, answered, title, description, answers in FORUM:
            rng = self.rng('forum', title)
            asked = now - timedelta(days=days_ago, hours=rng.randint(1, 10))
            question, created = Question.objects.get_or_create(author=self.users[username], title=title, defaults={
                'topic': topic, 'description': description, 'is_answered': answered,
            })
            self.tally('forum questions', created)
            if created:
                # created_at is filled in automatically, so move it back afterwards.
                # Giving updated_at the same time keeps the "edited" label off.
                Question.objects.filter(pk=question.pk).update(created_at=asked, updated_at=asked)
            if not Answer:
                continue

            # Each answer comes from a different demo user, never the one who asked
            others = [name for name in usernames if name != username]
            replied = asked
            for author, body in zip(rng.sample(others, len(answers)), answers):
                replied = min(replied + timedelta(hours=rng.randint(1, 6), minutes=rng.randint(0, 59)), now)
                reply, created = Answer.objects.get_or_create(forum=question, author=self.users[author], body=body)
                self.tally('forum answers', created)
                if created:
                    Answer.objects.filter(pk=reply.pk).update(created_at=replied, updated_at=replied)

    def print_summary(self):
        if self.removed:
            self.stdout.write(f'Reset: removed {self.removed} demo_ accounts and everything they owned.')
        for label in [*self.created, *(k for k in self.existing if k not in self.created)]:
            self.stdout.write(f'  {label}: {self.created[label]} created, {self.existing[label]} already there')
        if self.skipped:
            self.stdout.write(self.style.WARNING('Skipped:'))
            for part in self.skipped:
                self.stdout.write(f'  {part}')
        names = ', '.join(row[0] for row in USERS)
        self.stdout.write(self.style.SUCCESS(f'Demo data ready. Log in as {names} with the DEMO_PASSWORD setting.'))
