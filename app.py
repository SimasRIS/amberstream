from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from markupsafe import Markup
from datetime import datetime, timedelta, UTC
import os
import re

app = Flask(__name__)
# Production: Set SECRET_KEY via environment variable
# export SECRET_KEY='your-production-secret-key-here'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ambergrid-secret-key-dev')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///plans.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'admin_login'

# Database models
class Worker(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # Not hashed for demo

class Plan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)

class Meta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    last_updated = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

class Review(db.Model):
    """A customer review. Nothing is shown publicly until a worker approves it,
    so `approved` defaults to False — a public form is otherwise a spam target."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    location = db.Column(db.String(80))
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    approved = db.Column(db.Boolean, nullable=False, default=False)

@login_manager.user_loader
def load_user(user_id):
    return Worker.query.get(int(user_id))

# --- Presentation data -------------------------------------------------
# Nav is defined once here so every page renders the same menu (see base.html).
NAV = [
    ('home',           'Home',           'home'),
    ('about',          'About',          'about_page'),
    ('services',       'Services',       'services_page'),
    ('plans',          'Plans',          'plans_page'),
    ('reviews',        'Reviews',        'reviews_page'),
    ('sustainability', 'Sustainability', 'sustainability_page'),
    ('news',           'News',           'news_page'),
    ('contact',        'Contact',        'contact_page'),
]

# Selling points per plan. Sourced from the copy already on the services page;
# any plan not listed here falls back to DEFAULT_FEATURES so adding a plan in
# the admin console never renders an empty card.
PLAN_FEATURES = {
    'Basic Saver': [
        'Monthly billing, no fixed term',
        'Rate held until we publish a change',
        'Suits households and micro-businesses',
    ],
    'Green Fixed': [
        '100% renewable supply',
        '12-month fixed term',
        'Rate locked for the full term',
    ],
    'Business Flex': [
        'Tiered or time-of-use pricing',
        'Usage reports and load-shifting advice',
        'For SMEs and multi-site customers',
    ],
}

DEFAULT_FEATURES = [
    'Energy supply at the published rate',
    'Network charges and taxes billed separately',
    'Contact us for full terms',
]

PLAN_AUDIENCE = {
    'Basic Saver': 'Households, micro-businesses',
    'Green Fixed': '100% renewable preference',
    'Business Flex': 'SMEs, multi-site customers',
}


@app.context_processor
def inject_nav():
    """Make the nav available to every template without passing it per-route."""
    return {
        'nav_items': [
            {'id': key, 'label': label, 'url': url_for(endpoint)}
            for key, label, endpoint in NAV
        ]
    }


# ============================================================================
#  DELIBERATELY VULNERABLE — stored XSS in the customer review body.
#  ---------------------------------------------------------------------------
#  This is a localhost-only training target. The review body is rendered as raw
#  HTML after a weak, intentionally bypassable blocklist. Do NOT expose this app
#  to a network and do NOT point it at real data.
#
#  The blocklist strips <script> tags, javascript: URIs, and the four most
#  common inline event handlers (onerror/onload/onclick/onmouseover),
#  case-insensitively. Its gap — the intended bypass — is that it forgets every
#  OTHER handler, e.g. onfocus paired with autofocus:
#     <input autofocus onfocus=alert(document.cookie)>
#  The correct fix is output escaping (Jinja's default), not an input blocklist.
# ============================================================================
_XSS_BLOCKLIST = re.compile(
    r'(?i)(</?\s*script[^>]*>|javascript:|\bon(error|load|click|mouseover)\s*=)'
)


@app.template_filter('review_html')
def review_html(text):
    """Intentionally vulnerable: strip a few patterns, then trust the rest as
    raw HTML. Returning Markup marks it safe so it is injected unescaped."""
    return Markup(_XSS_BLOCKLIST.sub('', text or ''))


REVIEW_LIMITS = {'name': 80, 'location': 80, 'body': 1000}
REVIEW_BODY_MIN = 20


def validate_review(form):
    """Return (cleaned, errors). Length caps match the column widths so a long
    submission is rejected with a message rather than silently truncated."""
    cleaned = {
        'name': form.get('name', '').strip(),
        'location': form.get('location', '').strip(),
        'rating': form.get('rating', '').strip(),
        'body': form.get('body', '').strip(),
    }
    errors = {}

    if len(cleaned['name']) < 2:
        errors['name'] = 'Please tell us your name.'
    elif len(cleaned['name']) > REVIEW_LIMITS['name']:
        errors['name'] = 'Please keep your name under %d characters.' % REVIEW_LIMITS['name']

    if len(cleaned['location']) > REVIEW_LIMITS['location']:
        errors['location'] = 'Please keep this under %d characters.' % REVIEW_LIMITS['location']

    try:
        rating = int(cleaned['rating'])
        if not 1 <= rating <= 5:
            raise ValueError
    except ValueError:
        rating = None
        errors['rating'] = 'Please choose a rating from 1 to 5.'
    cleaned['rating'] = rating

    if len(cleaned['body']) < REVIEW_BODY_MIN:
        errors['body'] = 'Please write at least %d characters.' % REVIEW_BODY_MIN
    elif len(cleaned['body']) > REVIEW_LIMITS['body']:
        errors['body'] = 'Please keep your review under %d characters.' % REVIEW_LIMITS['body']

    return cleaned, errors


def published_reviews(limit=None):
    q = Review.query.filter_by(approved=True).order_by(Review.submitted_at.desc())
    return q.limit(limit).all() if limit else q.all()


def review_summary():
    """Average score and count across published reviews, for the page header."""
    reviews = Review.query.filter_by(approved=True).all()
    if not reviews:
        return {'count': 0, 'average': None}
    return {
        'count': len(reviews),
        'average': round(sum(r.rating for r in reviews) / len(reviews), 1),
    }


def plan_context():
    """Plan data shared by the pages that show rates."""
    plans = Plan.query.order_by(Plan.price).all()
    cheapest = min(plans, key=lambda p: p.price) if plans else None
    return {
        'plans': plans,
        'meta': Meta.query.first(),
        'cheapest_id': cheapest.id if cheapest else None,
        'plan_features': PLAN_FEATURES,
        'default_features': DEFAULT_FEATURES,
        'plan_audience': PLAN_AUDIENCE,
    }

# Sample customer reviews, written into an empty database on first run so the
# reviews page and the moderation queue are not blank on a fresh checkout.
# (name, town, rating, days_ago, approved, body)
SAMPLE_REVIEWS = [
    (
        'Rūta Kazlauskienė', 'Vilnius', 5, 214, True,
        "Switched from our old supplier to Green Fixed in February and the whole "
        "thing took about ten minutes online. No engineer visit, no gap in supply, "
        "and the first bill arrived on the date they said it would. What sold me "
        "was that the rate is genuinely locked for the twelve months - I read the "
        "terms twice looking for the catch and there isn't one."
    ),
    (
        'Mārtiņš Ozols', 'Riga', 4, 189, True,
        "Good supplier, fair rate on Basic Saver, and I like that the price page "
        "shows when it was last updated instead of hiding it. My one complaint is "
        "the billing portal - it works, but it logs you out constantly and there's "
        "no way to download a year of bills in one go. Four stars because the "
        "energy side is solid; the software could use some attention."
    ),
    (
        'Kertu Sepp', 'Tartu', 5, 165, True,
        "I emailed on a Tuesday afternoon about a meter reading that looked wrong "
        "and had a reply from an actual person before the end of the day. She "
        "explained how the estimate was calculated, corrected it, and the credit "
        "showed up on the next bill without me chasing it. That is the entire "
        "reason I stay."
    ),
    (
        'Tomas Vaitkus', 'Klaipėda', 3, 142, True,
        "The supply and the pricing are fine - no argument there. But the move to "
        "the new billing system in spring was messy. I got two estimated bills in a "
        "row despite submitting my own readings, and it took three emails to sort "
        "out. Credit where it's due: once someone senior picked it up it was fixed "
        "properly and they refunded the difference. Still, it should not have "
        "needed three emails."
    ),
    (
        'Ingrida Petraitytė', 'Kaunas', 5, 121, True,
        "We moved to Green Fixed specifically because the supply is hydro rather "
        "than a certificate-shuffling exercise, and AmberStream were the only ones "
        "who would actually tell me which stations the power comes from when I "
        "asked. That transparency is rare. Rate is competitive too, which I did not "
        "expect from a renewable tariff."
    ),
    (
        'Jānis Bērziņš', 'Liepāja', 2, 98, True,
        "Two stars, and I want to be fair about why. The tariff itself is one of "
        "the better ones I have had. But when my direct debit failed because my "
        "bank reissued my card, the first I heard about it was a late payment "
        "notice. No email, no text, no warning. I called and it was sorted in "
        "fifteen minutes, and the fee was waived without me having to argue - but "
        "a single automated reminder would have avoided all of it."
    ),
    (
        'Andrus Tamm', 'Tallinn', 4, 76, True,
        "We run three small workshops on Business Flex. The time-of-use pricing has "
        "cut about eleven percent off our monthly spend simply because the usage "
        "reports made it obvious we were running the compressors at the worst "
        "possible hour. The reports are genuinely useful rather than decorative. "
        "Docking a star only because consolidating three sites onto one invoice "
        "took longer to arrange than it should have."
    ),
    (
        'Gintarė Šimkutė', 'Panevėžys', 5, 54, True,
        "Signed a twelve-month fix last autumn, mostly out of caution. When "
        "wholesale prices jumped in January my neighbours were all comparing "
        "horror stories and my bill did not move by a cent. The fix did exactly "
        "what it said on the tin. Renewed without shopping around, which is not "
        "something I usually do."
    ),
    (
        'Laura Krastiņa', 'Jelgava', 4, 33, True,
        "Moved house in July and transferring the account was refreshingly boring - "
        "filled in one form, gave the closing reading, and the final bill and the "
        "new account both arrived correctly. No overlap, no double charging. The "
        "only reason this is not five stars is that I had to find the moving-house "
        "form myself; nobody mentioned it existed when I first called."
    ),
    (
        'Marius Adomaitis', 'Šiauliai', 5, 17, True,
        "Small bakery, four ovens, and electricity is our second biggest cost after "
        "flour. The tiered pricing on Business Flex suits us far better than the "
        "flat rate we were on, and the load-shifting advice was practical rather "
        "than generic - they looked at our actual half-hourly data and told us to "
        "move one proving cycle. Paid for itself in a month."
    ),
    # The last two are left unapproved so the moderation queue has real work in it.
    (
        'Eva Lepik', 'Pärnu', 4, 4, False,
        "Six months in and no complaints worth writing down. Bills arrive when they "
        "say, the readings match my own, and the rate is what I signed up for. "
        "Would be five stars with a proper mobile app - the website works on a "
        "phone but you can tell it was not designed for one."
    ),
    (
        'Dovydas Norkus', 'Alytus', 3, 1, False,
        "Decent enough. The rate is competitive and switching was painless, but I "
        "have been waiting eight days for an answer about whether my solar export "
        "can be credited against the same account. Two follow-ups, still nothing. "
        "Happy to revise this upwards if someone gets back to me."
    ),
]


# --- Startup DB setup with app context (Flask 3.1+ recommended) ---
def setup_db():
    db.create_all()
    if not Worker.query.filter_by(username='admin').first():
        db.session.add(Worker(username='admin', password='admin'))
    if not Plan.query.first():
        db.session.add_all([
            Plan(name='Basic Saver', price=0.12),
            Plan(name='Green Fixed', price=0.13),
            Plan(name='Business Flex', price=0.15)
        ])
    if not Meta.query.first():
        db.session.add(Meta(last_updated=datetime.now(UTC)))
    if not Review.query.first():
        now = datetime.now(UTC)
        db.session.add_all([
            Review(name=name, location=town, rating=rating, body=body,
                   submitted_at=now - timedelta(days=days_ago), approved=approved)
            for name, town, rating, days_ago, approved, body in SAMPLE_REVIEWS
        ])
    db.session.commit()

with app.app_context():
    setup_db()
# ---------------------------------------------------------------

# Homepage - Main domain
@app.route('/')
def home():
    return render_template('AmberStream.html', page='home',
                           recent_reviews=published_reviews(limit=3),
                           review_summary=review_summary(),
                           **plan_context())

# Admin login page
@app.route('/admin', methods=['GET', 'POST'])
@app.route('/admin/', methods=['GET', 'POST'])
def admin_login():
    msg = ''
    if request.method == 'POST':
        user = Worker.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('plans_admin'))
        else:
            msg = 'Invalid credentials'
    return render_template('admin/login.html', msg=msg)

@app.route('/admin/plans', methods=['GET', 'POST'])
@login_required
def plans_admin():
    msg = ''
    if request.method == 'POST':
        for plan in Plan.query.all():
            np = request.form.get(f'price_{plan.id}')
            if np is not None:
                try:
                    plan.price = float(np)
                except ValueError:
                    pass
        meta = Meta.query.first()
        meta.last_updated = datetime.now(UTC)
        db.session.commit()
        msg = 'Prices saved!'
    plans = Plan.query.order_by(Plan.price).all()
    meta = Meta.query.first()
    return render_template('admin/plans.html', plans=plans, msg=msg, meta=meta)

@app.route('/admin/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    msg = ''
    ok = False
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate old password
        if current_user.password != old_password:
            msg = 'Current password is incorrect!'
        elif not new_password:
            msg = 'New password cannot be empty!'
        elif len(new_password) < 3:
            msg = 'New password must be at least 3 characters!'
        elif new_password != confirm_password:
            msg = 'New passwords do not match!'
        else:
            # Update password
            current_user.password = new_password
            db.session.commit()
            msg = 'Password changed successfully!'
            ok = True

    return render_template('admin/password.html', msg=msg, ok=ok)

@app.route('/admin/reviews')
@login_required
def reviews_admin():
    return render_template(
        'admin/reviews.html',
        pending=Review.query.filter_by(approved=False)
                            .order_by(Review.submitted_at.desc()).all(),
        published=Review.query.filter_by(approved=True)
                              .order_by(Review.submitted_at.desc()).all(),
        msg=request.args.get('msg', ''),
    )

# POST-only on purpose: a GET route here could be fired by an <img> tag on any
# page a signed-in worker happens to visit.
@app.route('/admin/reviews/<int:review_id>/<action>', methods=['POST'])
@login_required
def review_action(review_id, action):
    review = db.session.get(Review, review_id)
    if review is None:
        abort(404)

    if action == 'approve':
        review.approved = True
        msg = 'Review published.'
    elif action == 'hide':
        review.approved = False
        msg = 'Review hidden from the public site.'
    elif action == 'delete':
        db.session.delete(review)
        msg = 'Review deleted.'
    else:
        abort(400)

    db.session.commit()
    return redirect(url_for('reviews_admin', msg=msg))

@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('admin_login'))

@app.route('/api/plans')
def api_plans():
    plans = Plan.query.all()
    meta = Meta.query.first()
    cheapest = min([plan.price for plan in plans]) if plans else None
    return {
        'plans': [
            {'name': plan.name, 'price': plan.price} for plan in plans
        ],
        'last_updated': meta.last_updated.isoformat() if meta else None,
        'cheapest': cheapest
    }

# --- Serve all site pages via Flask templates ---
@app.route('/about.html')
def about_page():
    return render_template('about.html', page='about')

@app.route('/AmberStream.html')
def amberstream_page():
    # Legacy URL from the static-site version; the homepage now lives at /.
    return redirect(url_for('home'), code=301)

@app.route('/contact.html')
def contact_page():
    return render_template('contact.html', page='contact')

@app.route('/plans.html')
def plans_page():
    return render_template('plans.html', page='plans', **plan_context())

@app.route('/news.html')
def news_page():
    return render_template('news.html', page='news')

@app.route('/services.html')
def services_page():
    return render_template('services.html', page='services', **plan_context())

@app.route('/sustainability.html')
def sustainability_page():
    return render_template('sustainability.html', page='sustainability')

@app.route('/reviews.html', methods=['GET', 'POST'])
def reviews_page():
    form, errors = {'name': '', 'location': '', 'rating': '', 'body': ''}, {}

    if request.method == 'POST':
        # Honeypot: a field hidden from people, so anything in it is a bot.
        # Answer as if it succeeded rather than telling the bot it was caught.
        if request.form.get('website'):
            return redirect(url_for('reviews_page', sent=1))

        form, errors = validate_review(request.form)
        if not errors:
            db.session.add(Review(
                name=form['name'],
                location=form['location'] or None,
                rating=form['rating'],
                body=form['body'],
            ))
            db.session.commit()
            # POST/redirect/GET so a refresh cannot resubmit the review.
            return redirect(url_for('reviews_page', sent=1))

    return render_template(
        'reviews.html',
        page='reviews',
        reviews=published_reviews(),
        summary=review_summary(),
        form=form,
        errors=errors,
        sent=request.args.get('sent') == '1',
        limits=REVIEW_LIMITS,
        body_min=REVIEW_BODY_MIN,
    )

if __name__ == '__main__':
    # Development only - use gunicorn for production
    app.run(debug=False, host='0.0.0.0', port=5000)
