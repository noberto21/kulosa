from django.core.management.base import BaseCommand

from apps.events.models import Category

# The 14 categories from the project specification. Slugs for the first eleven
# match the Phase 1 categories so existing links keep working.
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


class Command(BaseCommand):
    help = "Create the specification's event categories. Safe to run repeatedly."

    def handle(self, *args, **options):
        created = 0
        for slug, name, blurb in CATEGORIES:
            obj, was_created = Category.objects.get_or_create(slug=slug, defaults={"name": name, "description": blurb})
            if not was_created and not obj.description:
                obj.description = blurb
                obj.save(update_fields=["description"])
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"{created} created, {len(CATEGORIES) - created} already present."))
