# all the imports
import os
import sqlite3
from contextlib import closing

from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash

CURRENCY = {"uk": u"\u00A3", "cn": u"\u00A5"}

msg = dict()

# create our little application :)
app = Flask(__name__)

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.dirname(__file__)+'/tmp/flatshare.db',
    DEBUG=True,
    SECRET_KEY='rubyonrailstutorial',
    USERNAME='admin',
    PASSWORD='admin'
))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


@app.route('/')
def front():
    msg["error"] = None
    return render_template('front.html', msg=msg)


@app.route('/bills')
def bills():
    msg["error"] = None
    if not session.get('logged_in'):
        msg["error"] = "Please log in first"
        return render_template('bills.html', msg=msg)
    else:
        # fetch all the members
        cur = g.db.execute('select member_name, member_id from members where flat_id=?',
                           [session.get('flat_id'), ])

        members = [dict(member_name=row[0], member_id=row[1]) for row in cur.fetchall()]
        if not members:
            msg["error"] = "Please add a member in manage page first"

        # id to name mapping dictionary
        d = dict()
        for member in members:
            d[member["member_id"]] = member["member_name"]

        # fetch all the bills
        cur = g.db.execute(
            "select content, amount, created_time, bills.member_id "
            "from bills inner join members on bills.member_id=members.member_id "
            "where flat_id=? order by bills.bill_id desc",
            [session.get('flat_id'), ]
        )
        bills = [dict(content=row[0], amount=row[1], created_time=row[2], member_name=d[row[3]]) for row in cur.fetchall()]

        # compute the total amount
        total = 0
        for entry in bills:
            total += entry["amount"]

        msg["bills"] = bills
        msg["members"] = members
        msg["total"] = total
        return render_template('bills.html', msg=msg)


@app.route('/add', methods=['POST'])
def add_bill():
    if not session.get('logged_in'):
        abort(401)
    content = request.form['content']
    amount = request.form['amount']
    member_id = request.form['member_id']
    if amount.isdigit():
        g.db.execute('insert into bills (content, amount, member_id) values (?, ?, ?)',
                     [content, amount, member_id])
        g.db.commit()
        flash('New bill was successfully added')
        return redirect(url_for('bills'))
    else:
        msg["error"] = "Please input a number in amount"
        return render_template('bills.html', msg=msg)


@app.route('/analysis', methods=['GET'])
def analysis():
    msg["error"] = None
    if not session.get('logged_in'):
        msg["error"] = "Please log in first"
        return render_template('analysis.html', msg=msg)
    else:
        # fetch all the members
        cur = g.db.execute('select member_name, member_id from members where flat_id=?',
                           [session.get('flat_id'), ])
        members = [dict(member_name=row[0], member_id=row[1]) for row in cur.fetchall()]
        if not members:
            msg["error"] = "Please add a member in manage page first"

        # get member number
        member_number = len(members)

        # id to name mapping dictionary
        d = dict()
        for member in members:
            d[member["member_id"]] = member["member_name"]

        # fetch all the bills
        cur = g.db.execute(
            "select content, amount, bills.member_id "
            "from bills inner join members on bills.member_id=members.member_id "
            "where flat_id=? order by bills.bill_id desc",
            [session.get('flat_id'), ]
        )
        bills = [dict(content=row[0], amount=row[1], member_name=d[row[2]]) for row in cur.fetchall()]

        # initialise the result dictionary
        results = dict()
        for member in members:
            d[member["member_id"]] = member["member_name"]
            results[member["member_name"]] = 0

        # compute total amount and each amount
        total = 0
        for bill in bills:
            total += bill["amount"]
            results[bill["member_name"]] += bill["amount"]

        # prevent divided by zero
        if member_number != 0:
            average = total / member_number
        else:
            average = total

        average = round(average, 2)

        # compute the result
        for result in results:
            results[result] -= average

        msg["results"] = results
        msg["total"] = total
        return render_template('analysis.html', msg=msg)


@app.route('/manage', methods=['GET', 'POST'])
def manage():
    msg["error"] = None
    if not session.get('logged_in'):
        msg["error"] = "Please log in first"
    else:
        cur = g.db.execute('select member_name from members where flat_id=?',
                           [session.get('flat_id'), ])
        msg["members"] = [dict(member_name=row[0]) for row in cur.fetchall()]
        msg["member_number"] = len(msg["members"])

    if request.method == 'POST':
        member_name = request.form['member_name']
        cur = g.db.execute('select member_name from members where member_name=? and flat_id=?',
                           [member_name, session.get('flat_id')])
        if not cur.fetchall():
            g.db.execute('insert into members (member_name, flat_id) values (?, ?)',
                         [member_name, session.get('flat_id')])
            g.db.commit()
            msg["members"].append({"member_name": member_name})
            flash('New member was successfully added')
        else:
            msg["error"] = 'Exisitng member name'
    return render_template('manage.html', msg=msg)


@app.route('/change_location', methods=['POST'])
def change_location():
    msg["error"] = None
    if not session.get('logged_in'):
        msg["error"] = "Please log in first"
    if request.method == 'POST':
        country = request.form['country']
        g.db.execute('update flats set country=? where flat_name=?',
                     [country, session['flat_name']])
        g.db.commit()
        session["country"] = country
        session["currency"] = CURRENCY[session["country"]]
        flash('Your location was successfully changed')
        return redirect(url_for('manage'))
    return render_template('manage.html', msg=msg)


@app.route('/reset_flat', methods=['GET'])
def reset_flat():
    g.db.execute('delete from bills where member_id in (select member_id from members where flat_id=?)',
                 [session.get('flat_id'), ])
    g.db.execute('delete from members where flat_id=?',
                 [session.get('flat_id'), ])
    g.db.commit()
    flash('Your flat is reset')
    return render_template('manage.html', msg=msg)


@app.route('/clear_bills', methods=['GET'])
def clear_bills():
    g.db.execute('delete from bills where member_id in (select member_id from members where flat_id=?)',
                 [session.get('flat_id'), ])
    g.db.commit()
    flash('All your bills are cleared')
    return render_template('manage.html', msg=msg)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg["error"] = None
    if request.method == 'GET':
        if session.get('logged_in'):
            flash('You were logged in')
            return redirect(url_for('front'))
    if request.method == 'POST':
        flat_name = request.form['flat_name']
        password = request.form['password']
        cur = g.db.execute('select flat_name from flats where flat_name=?',
                           [flat_name, ])
        if not cur.fetchall():
            g.db.execute('insert into flats (flat_name, password) values (?, ?)',
                         [flat_name, password])
            g.db.commit()
            flash('Signup successfully, please log in')
            return render_template('login.html', msg=msg)
        else:
            msg["error"] = 'Occupied flat name'
    return render_template('signup.html', msg=msg)


@app.route('/login', methods=['GET', 'POST'])
def login():
    msg["error"] = None
    if request.method == 'POST':
        flat_name = request.form['flat_name']
        password = request.form['password']
        cur = g.db.execute('select flat_name, password, flat_id, country from flats where flat_name=?',
                           [flat_name, ])
        result = cur.fetchall()

        if not result:
            msg["error"] = 'Unexsistent username'
        elif password != result[0][1]:
            msg["error"] = 'Unmatched password'
        else:
            session['logged_in'] = True
            session['flat_name'] = flat_name
            session['flat_id'] = result[0][2]
            session["country"] = result[0][3]
            session["currency"] = CURRENCY[session["country"]]
            flash('Welcome back, ' + flat_name)
            return redirect(url_for('front'))
    return render_template('login.html', msg=msg)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('flat_name', None)
    session.pop('flat_id', None)
    flash('You were logged out')
    return redirect(url_for('front'))


if __name__ == '__main__':
    app.run()
