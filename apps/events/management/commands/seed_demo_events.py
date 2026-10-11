"""Developer-only sample listings so the UI has something to show locally.

Everything created is fictional, titled "[Demo] ...", and owned by a throwaway
account. Never run this against a real site: it refuses unless DEBUG is on
(or --force is given). Remove it all with --remove.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Category, Event, OrganizerProfile

DEMO_EMAIL = "demo-organizer@example.invalid"

# slug, title, category slug, day offset, hour, hours long, county, town, venue, price (None = free), summary
ROWS = [
    ("lakeside-sunset-sessions", "Lakeside Sunset Sessions", "music-concerts", 0, 17, 5, "Kisumu", "Kisumu", "Lakefront Grounds", 800, "An open-air evening of live bands with the sun going down over the water."),
    ("campus-tech-demo-night", "Campus Tech Demo Night", "technology-innovation", 0, 18, 3, "Kisii", "Kisii", "Innovation Hall", None, "Student teams show what they built this semester. Free to attend."),
    ("five-a-side-cup", "Five-a-Side Community Cup", "sports", 1, 9, 8, "Nairobi", "Nairobi", "Community Sports Ground", 300, "Neighbourhood teams compete across a full day of short matches."),
    ("rooftop-afrobeats-night", "Rooftop Afrobeats Night", "parties-nightlife", 2, 21, 6, "Nairobi", "Westlands", "Skyline Rooftop", 1500, "DJs, a rooftop dance floor and a late-night menu."),
    ("coast-food-spice-market", "Coast Food & Spice Market", "food-drink", 3, 11, 7, "Mombasa", "Mombasa", "Old Town Courtyard", None, "Street food stalls, spice sellers and live cooking demos."),
    ("founders-mixer", "Startup Founders Mixer", "business-networking", 3, 17, 3, "Nairobi", "Nairobi", "Co-working Space", 500, "Meet other founders over drinks and short lightning talks."),
    ("rift-valley-hike", "Rift Valley Sunrise Hike", "travel-outdoor", 4, 5, 6, "Nakuru", "Nakuru", "Trailhead Gate", 1200, "A guided half-day hike with breakfast at the summit."),
    ("poetry-spoken-word", "Poetry & Spoken Word Evening", "arts-culture", 5, 18, 3, "Kisumu", "Kisumu", "Arts Centre", 200, "Open mic and featured readers in a small, friendly room."),
    ("career-fair", "University Career & Internship Fair", "education-campus", 6, 9, 6, "Uasin Gishu", "Eldoret", "University Main Hall", None, "Employers meet students. Bring copies of your CV."),
    ("street-carnival", "Street Carnival Weekend", "festivals-carnivals", 8, 12, 9, "Nairobi", "Nairobi", "City Park", 600, "Parades, food trucks and live stages across a whole weekend."),
    ("river-clean-up", "River Clean-Up Saturday", "community-charity", 9, 8, 4, "Kisumu", "Kisumu", "Riverside Bridge", None, "Gloves and bags provided. Come with friends and good shoes."),
    ("choir-showcase", "Choir Showcase Night", "music-concerts", 11, 16, 4, "Nakuru", "Nakuru", "Town Theatre", 400, "Six choirs, one stage and a shared finale."),
    ("hackathon-weekend", "Build for Kenya Hackathon", "technology-innovation", 14, 9, 30, "Nairobi", "Nairobi", "Tech Hub", None, "Teams of up to four build working prototypes in one weekend."),
    ("sunday-fun-run", "Sunday Fun Run 5K", "sports", 5, 7, 3, "Mombasa", "Nyali", "Beach Road Start Line", 250, "A relaxed 5K for all paces, with a post-run breakfast."),
]


class Command(BaseCommand):
    help = "Create (or --remove) clearly labelled sample events for local development."

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="Delete all sample events and the sample account.")
        parser.add_argument("--force", action="store_true", help="Allow running when DEBUG is off.")

    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("Refusing to create sample events while DEBUG is off. Use --force only if you really mean it.")
        if opts["remove"]:
            deleted, _ = Event.objects.filter(owner__email=DEMO_EMAIL).delete()
            User.objects.filter(email=DEMO_EMAIL).delete()
            self.stdout.write(self.style.SUCCESS("Sample events removed."))
            return

        call_command("seed_categories", verbosity=0)
        owner, _ = User.objects.get_or_create(email=DEMO_EMAIL, defaults={"full_name": "Demo Organizer"})
        owner.set_unusable_password()
        owner.save()
        organizer, _ = OrganizerProfile.objects.get_or_create(owner=owner, defaults={"name": "Demo Events Collective"})

        now = timezone.localtime()
        made = 0
        for slug, title, cat, day, hour, hours, county, town, venue, price, summary in ROWS:
            start = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=day)
            _, created = Event.objects.update_or_create(
                slug=f"demo-{slug}",
                defaults=dict(
                    title=f"[Demo] {title}", summary=summary,
                    description=summary + "\n\nThis is sample content created for local development.",
                    category=Category.objects.get(slug=cat), owner=owner, organizer=organizer,
                    start_datetime=start, end_datetime=start + timedelta(hours=hours),
                    venue_name=venue, address="", county=county, town=town,
                    is_free=price is None, ticket_price=price, booking_url="" if price is None else "https://example.com/demo-tickets",
                    status=Event.Status.PUBLISHED, is_featured=slug in {"lakeside-sunset-sessions", "five-a-side-cup", "career-fair"},
                ),
            )
            made += created
        self.stdout.write(self.style.SUCCESS(f"{made} sample events created, {len(ROWS) - made} refreshed. Remove with --remove."))
