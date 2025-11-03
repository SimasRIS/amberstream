from flask import Flask, render_template, render_template_string, request, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, UTC
import os

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

@login_manager.user_loader
def load_user(user_id):
    return Worker.query.get(int(user_id))

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
    db.session.commit()

with app.app_context():
    setup_db()
# ---------------------------------------------------------------

# Homepage - Main domain
@app.route('/')
def home():
    return render_template('AmberStream.html')

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
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
  <title>AmberStream Worker Login</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body style="background:#ffffff;">
  <div class="page-frame" style="max-width:400px;margin:54px auto;">
    <table class="hdr"><tr><td class="hdr-cell">
      <img src="{{ url_for('static', filename='amberstream.png') }}" class="hdr-logo" alt="AmberStream Logo">
      <div class="hdr-text">
        <h1>AmberStream</h1>
        <p class="tagline">Reliable • Sustainable • Affordable Energy for Everyone</p>
      </div>
    </td></tr></table>
    <div class="content" style="padding:30px 24px 18px 24px; text-align:center;">
      <h2 class="section-title">Worker Login</h2>
      {% if msg %}<div style="color:red;">{{ msg }}</div>{% endif %}
      <form method="POST" style="max-width:260px;margin:auto;">
        <input name="username" placeholder="Username"><br>
        <input name="password" type="password" placeholder="Password"><br>
        <button type="submit" class="btn" style="margin-top:14px;width:100%;">Login</button>
      </form>
    </div>
  </div>
</body>
</html>
''', msg=msg)

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
    plans = Plan.query.all()
    meta = Meta.query.first()
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Edit Electricity Plans – AmberStream</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body style="background:#ffffff;">
  <div class="page-frame" style="max-width:700px;margin:48px auto;">
    <table class="hdr"><tr><td class="hdr-cell">
      <img src="{{ url_for('static', filename='amberstream.png') }}" class="hdr-logo" alt="AmberStream Logo">
      <div class="hdr-text">
        <h1>AmberStream</h1>
        <p class="tagline">Reliable • Sustainable • Affordable Energy for Everyone</p>
      </div>
    </td></tr></table>
    <div class="content" style="padding:25px 20px;max-width:430px;margin:auto;text-align:center;">
      <h2 class="section-title">Edit Electricity Plan Prices</h2>
      {% if msg %}<div style="color:green;margin-bottom:10px;">{{ msg }}</div>{% endif %}
      <form method="POST">
        <table class="highlight" style="margin:auto;width:100%;">
          <tr><th>Plan</th><th>Energy Rate (€ / kWh)</th></tr>
          {% for plan in plans %}
            <tr>
              <td><b>{{ plan.name }}</b></td>
              <td><input name="price_{{ plan.id }}" value="{{ plan.price }}" step="0.01" style="width:80px"> €/kWh</td>
            </tr>
          {% endfor %}
        </table>
        <button class="btn" type="submit" style="margin-top:16px;width:100%;">Save All</button>
      </form>
      <div style="font-size:12px;color:#555;margin-top:8px;">Last updated: {{ meta.last_updated.strftime('%Y-%m-%d %H:%M:%S') if meta else '?' }}</div>
      <div style="margin-top:10px;text-align:right;">
        <a href="{{ url_for('change_password') }}">Change Password</a> | 
        <a href="{{ url_for('logout') }}">Logout</a>
      </div>
    </div>
  </div>
</body>
</html>
''', plans=plans, msg=msg, meta=meta)

@app.route('/admin/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    msg = ''
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
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Change Password – AmberStream</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body style="background:#ffffff;">
  <div class="page-frame" style="max-width:500px;margin:48px auto;">
    <table class="hdr"><tr><td class="hdr-cell">
      <img src="{{ url_for('static', filename='amberstream.png') }}" class="hdr-logo" alt="AmberStream Logo">
      <div class="hdr-text">
        <h1>AmberStream</h1>
        <p class="tagline">Reliable • Sustainable • Affordable Energy for Everyone</p>
      </div>
    </td></tr></table>
    <div class="content" style="padding:25px 20px;max-width:400px;margin:auto;text-align:center;">
      <h2 class="section-title">Change Password</h2>
      {% if msg %}
        <div style="color:{% if 'successfully' in msg %}green{% else %}red{% endif %};margin-bottom:10px;padding:10px;border-radius:4px;background:{% if 'successfully' in msg %}#e8f5e9{% else %}#ffebee{% endif %};">{{ msg }}</div>
      {% endif %}
      <form method="POST" style="max-width:300px;margin:auto;">
        <div style="text-align:left;margin-bottom:15px;">
          <label style="display:block;margin-bottom:5px;font-weight:bold;">Current Password:</label>
          <input name="old_password" type="password" placeholder="Enter current password" required style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
        </div>
        <div style="text-align:left;margin-bottom:15px;">
          <label style="display:block;margin-bottom:5px;font-weight:bold;">New Password:</label>
          <input name="new_password" type="password" placeholder="Enter new password" required style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
        </div>
        <div style="text-align:left;margin-bottom:15px;">
          <label style="display:block;margin-bottom:5px;font-weight:bold;">Confirm New Password:</label>
          <input name="confirm_password" type="password" placeholder="Confirm new password" required style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;">
        </div>
        <button class="btn" type="submit" style="margin-top:16px;width:100%;">Change Password</button>
      </form>
      <div style="margin-top:20px;text-align:center;">
        <a href="{{ url_for('plans_admin') }}">← Back to Plans</a> | 
        <a href="{{ url_for('logout') }}">Logout</a>
      </div>
    </div>
  </div>
</body>
</html>
''', msg=msg)

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
    return render_template('about.html')

@app.route('/AmberStream.html')
def amberstream_page():
    return render_template('AmberStream.html')

@app.route('/contact.html')
def contact_page():
    return render_template('contact.html')

@app.route('/plans.html')
def plans_page():
    return render_template('plans.html')

@app.route('/news.html')
def news_page():
    return render_template('news.html')

@app.route('/services.html')
def services_page():
    return render_template('services.html')

@app.route('/sustainability.html')
def sustainability_page():
    return render_template('sustainability.html')

if __name__ == '__main__':
    # Development only - use gunicorn for production
    app.run(debug=False, host='0.0.0.0', port=5000)
