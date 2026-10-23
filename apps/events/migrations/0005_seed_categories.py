from django.db import migrations


CATEGORIES = [
    ("music-concerts", "Music & Concerts", "Live shows, gigs and album launches"),
    ("sports", "Sports", "Matches, tournaments and fun runs"),
    ("festivals-carnivals", "Festivals & Carnivals", "Street culture and big weekends out"),
    ("parties-nightlife", "Parties & Nightlife", "Club nights, rooftops and after-parties"),
    ("business-networking", "Business & Networking", "Mixers, pitch nights and expos"),
    ("technology-innovation", "Technology & Innovation", "Meetups, hackathons and demo days"),
    ("education-campus", "Education & Campus Events", "Campus socials, fairs and talks"),
    ("arts-culture", "Arts & Culture", "Exhibitions, theatre and poetry"),
    ("food-drink", "Food & Drink", "Tastings, markets and cook-offs"),
    ("religious-events", "Religious Events", "Services, conventions and celebrations"),
    ("community-charity", "Community & Charity", "Clean-ups, drives and fundraisers"),
    ("conferences-workshops", "Conferences & Workshops", "Training, summits and masterclasses"),
    ("travel-outdoor", "Travel & Outdoor Activities", "Hikes, camping and day trips"),
    ("other-events", "Other Events", "Everything else worth knowing about"),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("events", "Category")
    for slug, name, description in CATEGORIES:
        Category.objects.using(schema_editor.connection.alias).get_or_create(
            slug=slug,
            defaults={"name": name, "description": description},
        )


class Migration(migrations.Migration):
    dependencies = [("events", "0004_remove_event_event_paid_needs_price_and_more")]

    operations = [migrations.RunPython(seed_categories, migrations.RunPython.noop)]
