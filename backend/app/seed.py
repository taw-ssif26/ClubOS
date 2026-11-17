"""Default plans + site copy. Seeding only INSERTS MISSING rows, so super-admin edits are never overwritten."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Plan, SiteContent

FLAGS = ["bulk_email", "conditional_logic", "waitlist", "advanced_themes", "advanced_analytics", "remove_branding"]


def L(members, admins, events, storage, emails, on: bool) -> dict:
    return {"members": members, "admins": admins, "active_events": events, "storage_mb": storage,
            "emails_per_day": emails, **{f: on for f in FLAGS}}


def f(label, status="live"):
    return {"label": label, "status": status}


DEFAULT_PLANS = [
    dict(key="free", name="Free", sort=0, price_monthly=0, price_label="৳0", cta_label="Start free",
         tagline="Everything a club needs to run itself.", highlighted=False,
         limits=L(100, 3, 5, 500, 0, False),
         features=[f("Club profile and public page"), f("Up to 100 members"), f("3 admin seats"),
                   f("Custom roles and permissions"), f("Posts and announcements"), f("5 active events"),
                   f("Event registration with custom form fields"), f("QR tickets and check-in"),
                   f("Participant management and CSV export"), f("Member applications"),
                   f("Basic customization: logo, banner, 3 themes, brand color"), f("Club calendar feed"),
                   f("500 MB file storage"), f("Basic analytics"), f("Ratings and reviews"),
                   f("Club and event discovery"), f("Certificates (limited)", "soon")]),
    dict(key="pro", name="Pro", sort=1, price_monthly=800, price_label="৳800", cta_label="Upgrade to Pro",
         tagline="For clubs that run a serious operation.", highlighted=True,
         limits=L(None, None, None, 5120, 5000, True),
         features=[f("Everything in Free"), f("Unlimited members, admins and active events"),
                   f("Conditional registration forms"), f("Waitlists with automatic promotion"),
                   f("Bulk, personalized and scheduled email"), f("Audience segments (who attended, who didn't)"),
                   f("All themes, custom colors and typography"), f("Advanced analytics and growth reports"),
                   f("Reduced ClubOS branding"), f("5 GB storage, 5,000 emails a day"),
                   f("Teams, departments and member tags", "soon"), f("Paid events, ticket types, promo codes", "soon"),
                   f("Automations (welcome emails, certificates, feedback)", "soon"),
                   f("Automated certificates with public verification", "soon"), f("Custom sender address", "soon")]),
    dict(key="organization", name="Organization", sort=2, price_monthly=3500, price_label="৳3,500", cta_label="Talk to us",
         tagline="For institutions running many clubs.", highlighted=False,
         limits=L(None, None, None, 51200, 50000, True),
         features=[f("Everything in Pro"), f("50 GB storage, 50,000 emails a day"),
                   f("Institution profile and verified badge"),
                   f("Central dashboard for every club", "soon"), f("Institution-wide announcements and events", "soon"),
                   f("Cross-club events", "soon"), f("Organization analytics and central moderation", "soon")]),
    dict(key="enterprise", name="Enterprise", sort=3, price_monthly=None, price_label="Custom", cta_label="Contact sales",
         tagline="White-label ClubOS for universities.", highlighted=False,
         limits=L(None, None, None, 512000, 500000, True),
         features=[f("Everything in Organization"), f("Custom domain and full white-label", "soon"),
                   f("SSO and advanced security", "soon"), f("API access and webhooks", "soon"),
                   f("Dedicated support and SLA", "soon")]),
]

DEFAULT_CONTENT = {
    "site.brand": {"name": "ClubOS", "tagline": "The operating system for clubs",
                   "contact_email": "hello@clubos.app", "facebook": "", "instagram": "", "x": ""},
    "nav": {"links": [{"label": "Discover", "href": "/discover"}, {"label": "Pricing", "href": "/pricing"}],
            "login_label": "Sign in", "cta_label": "Start a club"},
    "home.hero": {
        "title": "Stop running your club out of spreadsheets.",
        "subtitle": "Members, events, tickets and email in one place. Free for clubs of up to 100 people, with no card and no catch.",
        "cta_primary": {"label": "Start your club free", "href": "/new-club"},
        "cta_secondary": {"label": "Browse clubs", "href": "/discover"},
        "ticket": {"event": "Tech Carnival 2027", "club": "Robotics Club", "holder": "Rahim Uddin", "serial": "CLB-7F3A91"},
    },
    "home.proof": {"items": ["Registration forms", "QR check-in", "Bulk email", "Member roster", "Waitlists", "Ratings and reviews", "Calendar feeds", "CSV export"]},
    "home.problem": {
        "title": "Your club already has a system. It's five tabs and a group chat.",
        "body": "A form for registration, a sheet for attendance, WhatsApp for reminders, a doc for the roster. Every handover loses something. Every event repeats the same copy-paste."},
    "home.features": {"title": "One place for the whole operation", "items": [
        {"title": "Registration that checks itself", "body": "Build the form, cap the seats, confirm by email. Everyone gets a QR ticket."},
        {"title": "Check-in in seconds", "body": "Scan at the door from any phone. Duplicates and forged tickets are rejected on the spot."},
        {"title": "Roles that match your committee", "body": "Treasurer, media secretary, volunteer. Each person sees and changes only what they should."},
        {"title": "Email that knows your members", "body": "Message everyone who registered but didn't show up, by name, in one click."},
        {"title": "Handover without loss", "body": "Members, events and history stay with the club when the committee graduates."}]},
    "home.how": {"title": "From idea to first event in an afternoon", "steps": [
        {"title": "Create your club", "body": "Name, logo, and a public page at clubos.app/c/your-club."},
        {"title": "Open an event", "body": "Set the date, seats and the questions you need answered."},
        {"title": "Run the day", "body": "Scan tickets, watch attendance live, email attendees afterwards."}]},
    "home.reviews": {"title": "What clubs and members say"},
    "home.cta": {"title": "Move your club in this week.", "subtitle": "Free plan. No card. Your data stays exportable.", "button": "Start your club free"},
    "pricing.page": {
        "title": "Free to run a club. Paid to run an organization.",
        "subtitle": "Pay when you outgrow the free plan, not before. Prices in Bangladeshi taka, billed monthly.",
        "billing_note": "Payment by bKash, Nagad or bank transfer. We activate your plan within one working day.",
        "faq": [
            {"q": "Is the free plan really enough to run a club?", "a": "Yes. Registration, QR check-in, roles, posts, a public page and CSV export are all free. You upgrade for scale and automation."},
            {"q": "What happens if I downgrade?", "a": "Nothing is deleted. Existing members and events stay. You just can't add past the free limits until you upgrade again."},
            {"q": "How do I pay?", "a": "Request an upgrade from your club dashboard. We confirm payment by bKash, Nagad or bank transfer and switch your plan on."},
            {"q": "Can my institution manage many clubs?", "a": "The Organization plan is built for that. Talk to us and we'll set it up."}]},
    "discover.page": {"title": "Find your people", "subtitle": "Clubs and events open to everyone, ranked by what members actually think."},
    "legal.terms": {"title": "Terms of Service", "updated": "November 2026",
        "review_note": "Plain-language starting draft. Have a lawyer review it before launch.",
        "sections": [
            {"heading": "Using ClubOS", "body": "ClubOS lets clubs and student organizations run memberships, events, forms and email. You must give accurate information, keep your password private, and be old enough to agree to these terms where you live, or have a parent or guardian's permission."},
            {"heading": "Clubs and their members", "body": "People who create a club are responsible for how they use the data of the people who join or register. They may use it to run the club and its events and must not sell it or use it to harass anyone. ClubOS may suspend clubs or accounts that break these rules."},
            {"heading": "Your content", "body": "You keep ownership of what you post: club pages, event descriptions, images and reviews. You allow ClubOS to store and display it to operate the service. Do not post anything unlawful, hateful, misleading, or that you do not have the right to share."},
            {"heading": "Reviews", "body": "Reviews must come from real participation and describe your own experience. We may hide or remove reviews that are abusive, fake or off-topic."},
            {"heading": "Plans and payment", "body": "The Free plan is free. Paid plans are billed manually in Bangladeshi taka for the months you choose, and switch off automatically at the end of the period; nothing is deleted, but paid features and extra capacity stop. Prices can change for future periods."},
            {"heading": "Availability and liability", "body": "We work to keep ClubOS running but cannot promise it will always be available or error-free. To the extent the law allows, ClubOS is not liable for indirect losses, and our total liability is limited to what you paid us in the previous three months."},
            {"heading": "Ending your use", "body": "You can delete your account at any time from your security settings. We may suspend or close accounts that break these terms. These terms are governed by the laws of Bangladesh."}]},
    "legal.privacy": {"title": "Privacy Policy", "updated": "November 2026",
        "review_note": "Plain-language starting draft. Have a lawyer review it before launch.",
        "sections": [
            {"heading": "What we collect", "body": "Your name, email, username and a hashed password; optional profile details you add; the clubs you join and any answers you give on applications; event registrations and registration answers; reviews you write; images clubs upload; and technical data such as sign-in times, IP address and device type, which we use to keep accounts secure."},
            {"heading": "Who sees it", "body": "Club organizers can see the name, email and answers of people who join their club or register for their events. Your profile is private unless you make it public. Reviews show your first name and last initial. We do not sell personal data or show advertising."},
            {"heading": "Email", "body": "We send account and security emails, confirmations for events and clubs you join, and messages from clubs you belong to. Club messages include an unsubscribe link, and we honour it."},
            {"heading": "Service providers", "body": "We use hosting, database and email-delivery providers to run ClubOS. They process data only on our instructions."},
            {"heading": "How long we keep it", "body": "We keep your account while it is open. Sign-in history is deleted after 90 days and sent email records after 30 days. When you delete your account we remove your identity, reviews and sessions; clubs keep anonymous attendance totals."},
            {"heading": "Your choices", "body": "You can edit your profile, download all your data, change your password, turn on two-factor authentication, and delete your account from your security settings. To ask anything else, email us using the address on the contact page."}]},
    "footer": {"blurb": "ClubOS replaces the scattered tools clubs use with one connected operating system.",
               "columns": [{"title": "Product", "links": [{"label": "Discover", "href": "/discover"}, {"label": "Pricing", "href": "/pricing"}, {"label": "Start a club", "href": "/new-club"}]},
                           {"title": "Legal", "links": [{"label": "Terms of Service", "href": "/terms"}, {"label": "Privacy Policy", "href": "/privacy"}]}],
               "legal": "© ClubOS. Made in Bangladesh."},
}


def seed(db: Session) -> None:
    have_plans = set(db.scalars(select(Plan.key)))
    for p in DEFAULT_PLANS:
        if p["key"] not in have_plans:
            db.add(Plan(**p))
    have_content = set(db.scalars(select(SiteContent.key)))
    for k, v in DEFAULT_CONTENT.items():
        if k not in have_content:
            db.add(SiteContent(key=k, value=v))
    db.commit()
