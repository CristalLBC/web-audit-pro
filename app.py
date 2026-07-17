"""
Web Audit App - Scan websites for online presence gaps & sell fixes
"""

import os
import sqlite3
import json
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import stripe

from audit_engine import run_full_audit

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-this-to-a-random-secret')

# Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY', '')

# Admin login
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'change-this-password')

DB_PATH = os.path.join(os.path.dirname(__file__), 'leads.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            business_name TEXT,
            email TEXT,
            phone TEXT,
            issues TEXT,
            issue_count INTEGER DEFAULT 0,
            total_fix_cost REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            stripe_session_id TEXT,
            items TEXT,
            total REAL,
            customer_email TEXT,
            paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );
    ''')
    conn.commit()
    conn.close()


init_db()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# =========== ROUTES ===========

@app.route('/')
def index():
    return render_template('index.html', stripe_key=STRIPE_PUBLIC_KEY)


@app.route('/audit', methods=['POST'])
def audit():
    url = request.form.get('url', '').strip()
    if not url:
        return render_template('index.html', error='Please enter a website URL', stripe_key=STRIPE_PUBLIC_KEY)

    try:
        result = run_full_audit(url)
    except Exception as e:
        return render_template('index.html', error=f'Error scanning website: {str(e)}', stripe_key=STRIPE_PUBLIC_KEY)

    # Save lead to DB
    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO leads (url, business_name, issues, issue_count, total_fix_cost) VALUES (?, ?, ?, ?, ?)',
        (result['url'], result['business_name'], json.dumps(result['issues']),
         result['issue_count'], result['total_fix_cost'])
    )
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return render_template(
        'results.html',
        result=result,
        lead_id=lead_id,
        stripe_key=STRIPE_PUBLIC_KEY,
    )


@app.route('/api/lead/<int:lead_id>')
def get_lead(lead_id):
    conn = get_db()
    lead = conn.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()
    conn.close()
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    return jsonify(dict(lead))


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    data = request.get_json()
    lead_id = data.get('lead_id')
    items = data.get('items', [])

    if not items:
        return jsonify({'error': 'No items selected'}), 400

    conn = get_db()
    lead = conn.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()
    if not lead:
        conn.close()
        return jsonify({'error': 'Lead not found'}), 404

    email = data.get('email', '')
    phone = data.get('phone', '')

    # Update lead with contact info
    conn.execute('UPDATE leads SET email = ?, phone = ? WHERE id = ?', (email, phone, lead_id))

    line_items = []
    item_names = []

    for item in items:
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': item['title'],
                    'description': item.get('fix', item['title']),
                },
                'unit_amount': int(item['price'] * 100),  # cents
            },
            'quantity': 1,
        })
        item_names.append(item['title'])

    total = sum(item['price'] for item in items)

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=line_items,
            mode='payment',
            success_url=request.host_url + 'success?session_id={CHECKOUT_SESSION_ID}&lead_id=' + str(lead_id),
            cancel_url=request.host_url + 'results/' + str(lead_id),
            customer_email=email if email else None,
            metadata={
                'lead_id': str(lead_id),
                'items': json.dumps(item_names),
            }
        )

        # Save order
        conn.execute(
            'INSERT INTO orders (lead_id, stripe_session_id, items, total, customer_email) VALUES (?, ?, ?, ?, ?)',
            (lead_id, checkout_session.id, json.dumps(item_names), total, email)
        )
        conn.commit()
        conn.close()

        return jsonify({'session_id': checkout_session.id, 'url': checkout_session.url})
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/success')
def success():
    session_id = request.args.get('session_id', '')
    lead_id = request.args.get('lead_id', '')

    if session_id:
        conn = get_db()
        conn.execute('UPDATE orders SET paid = 1 WHERE stripe_session_id = ?', (session_id,))
        conn.commit()
        conn.close()

    return render_template('success.html', lead_id=lead_id)


@app.route('/results/<int:lead_id>')
def view_results(lead_id):
    conn = get_db()
    lead = conn.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()
    conn.close()

    if not lead:
        return 'Lead not found', 404

    result = {
        'url': lead['url'],
        'business_name': lead['business_name'],
        'issues': json.loads(lead['issues']),
        'issue_count': lead['issue_count'],
        'total_fix_cost': lead['total_fix_cost'],
    }
    return render_template('results.html', result=result, lead_id=lead_id, stripe_key=STRIPE_PUBLIC_KEY)


# =========== ADMIN ===========

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@login_required
def admin_dashboard():
    conn = get_db()
    leads = conn.execute('SELECT * FROM leads ORDER BY created_at DESC').fetchall()
    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()

    total_leads = len(leads)
    total_paid = sum(o['total'] for o in orders if o['paid'])
    total_orders = sum(1 for o in orders if o['paid'])

    return render_template(
        'admin.html',
        leads=[dict(l) for l in leads],
        orders=[dict(o) for o in orders],
        total_leads=total_leads,
        total_paid=total_paid,
        total_orders=total_orders,
    )


@app.route('/admin/lead/<int:lead_id>')
@login_required
def admin_lead_detail(lead_id):
    conn = get_db()
    lead = conn.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()
    orders = conn.execute('SELECT * FROM orders WHERE lead_id = ?', (lead_id,)).fetchall()
    conn.close()

    if not lead:
        return 'Lead not found', 404

    lead_dict = dict(lead)
    lead_dict['issues'] = json.loads(lead_dict['issues'])

    return render_template('admin_lead.html', lead=lead_dict, orders=[dict(o) for o in orders])


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'app': 'Web Audit Tool'})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
