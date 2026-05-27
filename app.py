import streamlit as st
st.set_page_config(page_title='SoleTrack', page_icon='👟', layout='wide')

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import hashlib

DB = r'C:\hesabuai\sneakers.db'

def get_conn():
    return sqlite3.connect(DB)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

# ── Init DB ──────────────────────────────────────────────────────────────────
def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        full_name TEXT,
        phone TEXT,
        is_active INTEGER DEFAULT 1,
        failed_attempts INTEGER DEFAULT 0,
        last_login TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY,
        shoe_name TEXT,
        size TEXT,
        quantity INTEGER,
        buying_price REAL,
        selling_price REAL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY,
        shoe_name TEXT,
        size TEXT,
        quantity INTEGER,
        selling_price REAL,
        total REAL,
        payment_method TEXT,
        served_by TEXT,
        date TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY,
        category TEXT,
        description TEXT,
        amount REAL,
        date TEXT,
        recorded_by TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY,
        name TEXT,
        phone TEXT,
        address TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS credit_stock (
        id INTEGER PRIMARY KEY,
        supplier_id INTEGER,
        supplier_name TEXT,
        shoe_name TEXT,
        quantity INTEGER,
        amount_owed REAL,
        amount_paid REAL DEFAULT 0,
        due_date TEXT,
        status TEXT DEFAULT 'Unpaid',
        date_added TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS credit_payments (
        id INTEGER PRIMARY KEY,
        credit_id INTEGER,
        amount REAL,
        payment_date TEXT,
        notes TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS returns (
        id INTEGER PRIMARY KEY,
        shoe_name TEXT,
        size TEXT,
        quantity INTEGER,
        reason TEXT,
        action TEXT,
        date TEXT,
        recorded_by TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY,
        username TEXT,
        action TEXT,
        details TEXT,
        date TEXT
    )''')

    # Default admin
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username,password,role,full_name,phone) VALUES (?,?,?,?,?)",
                  ('admin', hash_password('admin123'), 'Admin', 'Administrator', ''))

    conn.commit()
    conn.close()

init_db()

# ── Session State ─────────────────────────────────────────────────────────────
for key, val in [('logged_in', False), ('username', ''), ('role', ''),
                 ('full_name', ''), ('login_time', None)]:
    if key not in st.session_state:
        st.session_state[key] = val

def log_activity(username, action, details=''):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO activity_log (username,action,details,date) VALUES (?,?,?,?)",
              (username, action, details, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

# ── Payment Due Reminders ─────────────────────────────────────────────────────
def check_due_payments():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM credit_stock WHERE status != 'Paid'", conn)
    conn.close()
    if df.empty:
        return
    today = datetime.now().date()
    for _, row in df.iterrows():
        try:
            due = datetime.strptime(row['due_date'], '%Y-%m-%d').date()
            days_left = (due - today).days
            remaining = row['amount_owed'] - row['amount_paid']
            if days_left < 0:
                st.sidebar.error(f"⚠️ OVERDUE: {row['supplier_name']} - KES {remaining:,.0f}")
            elif days_left <= 3:
                st.sidebar.warning(f"🔔 Due in {days_left}d: {row['supplier_name']} - KES {remaining:,.0f}")
        except:
            pass

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title('👟 Sole Track')
        st.subheader('Please Login')
        st.divider()

        username = st.text_input('Username', placeholder='Enter username')
        password = st.text_input('Password', type='password', placeholder='Enter password')

        if st.button('Login', type='primary', use_container_width=True):
            if not username or not password:
                st.warning('Enter username and password')
            else:
                conn = get_conn()
                user = pd.read_sql(
                    "SELECT * FROM users WHERE username=? AND is_active=1",
                    conn, params=(username,))
                conn.close()

                if user.empty:
                    st.error('User not found')
                    log_activity(username, 'Failed Login', 'User not found')
                elif user.iloc[0]['failed_attempts'] >= 3:
                    st.error('Account locked! Contact admin.')
                elif verify_password(password, user.iloc[0]['password']):
                    # Reset failed attempts
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("UPDATE users SET failed_attempts=0, last_login=? WHERE username=?",
                              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), username))
                    conn.commit()
                    conn.close()

                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user.iloc[0]['role']
                    st.session_state.full_name = user.iloc[0]['full_name']
                    st.session_state.login_time = datetime.now()

                    log_activity(username, 'Login', 'Successful login')
                    st.success(f'Welcome {user.iloc[0]["full_name"]}!')
                    st.rerun()
                else:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("UPDATE users SET failed_attempts=failed_attempts+1 WHERE username=?",
                              (username,))
                    conn.commit()
                    conn.close()
                    attempts = int(user.iloc[0]['failed_attempts']) + 1
                    remaining = 3 - attempts
                    if remaining > 0:
                        st.error(f'Wrong password! {remaining} attempts left.')
                    else:
                        st.error('Account locked! Contact admin.')
                    log_activity(username, 'Failed Login', 'Wrong password')

        st.divider()
        st.caption('Default: username=admin, password=admin123')
        st.caption('Change password after first login')

# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
else:
    role = st.session_state.role

    # Session timeout check
    if st.session_state.login_time:
        elapsed = datetime.now() - st.session_state.login_time
        if elapsed > timedelta(minutes=60):
            st.session_state.logged_in = False
            st.session_state.username = ''
            st.session_state.role = ''
            st.warning('Session expired! Please login again.')
            st.rerun()

    # Header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.title('👟 SoleTrack - Sneaker Manager')
    with col2:
        st.caption(f'{st.session_state.full_name}')
        st.caption(f'Role: {role}')
    with col3:
        if st.button('Logout'):
            log_activity(st.session_state.username, 'Logout', 'User logged out')
            for key in ['logged_in', 'username', 'role', 'full_name', 'login_time']:
                st.session_state[key] = False if key == 'logged_in' else (None if key == 'login_time' else '')
            st.rerun()

    # Payment reminders
    check_due_payments()

    # Build menu
    menu = ['Dashboard', 'Stock', 'Record Sale']
    if role in ['Admin', 'Manager', 'Cashier']:
        menu.append('Expenses')
    if role in ['Admin', 'Manager']:
        menu.extend(['Returns', 'Suppliers & Credit', 'Analytics', 'AI Advisor'])
    if role == 'Admin':
        menu.extend(['User Management', 'Activity Log', 'Change Password'])

    page = st.sidebar.radio('Menu', menu)
    st.sidebar.divider()
    if st.session_state.login_time:
        elapsed_min = int((datetime.now() - st.session_state.login_time).total_seconds() / 60)
        st.sidebar.caption(f'Session: {60 - elapsed_min} min left')

    # ── DASHBOARD ──────────────────────────────────────────────────────────────
    if page == 'Dashboard':
        st.header('📊 Dashboard')
        conn = get_conn()
        stock_df = pd.read_sql("SELECT * FROM stock", conn)
        sales_df = pd.read_sql("SELECT * FROM sales", conn)
        expenses_df = pd.read_sql("SELECT * FROM expenses", conn)
        credit_df = pd.read_sql("SELECT * FROM credit_stock WHERE status != 'Paid'", conn)
        conn.close()

        c1, c2, c3, c4 = st.columns(4)
        total_stock_value = (stock_df['quantity'] * stock_df['buying_price']).sum() if not stock_df.empty else 0
        total_sales = sales_df['total'].sum() if not sales_df.empty else 0
        total_expenses = expenses_df['amount'].sum() if not expenses_df.empty else 0
        total_credit_owed = (credit_df['amount_owed'] - credit_df['amount_paid']).sum() if not credit_df.empty else 0

        c1.metric('Stock Value', f'KES {total_stock_value:,.0f}')
        c2.metric('Total Sales', f'KES {total_sales:,.0f}')
        c3.metric('Total Expenses', f'KES {total_expenses:,.0f}')
        c4.metric('Credit Owed', f'KES {total_credit_owed:,.0f}')

        st.divider()
        if not sales_df.empty:
            st.subheader('Recent Sales')
            st.dataframe(sales_df.tail(10), use_container_width=True)

    # ── STOCK ──────────────────────────────────────────────────────────────────
    elif page == 'Stock':
        st.header('📦 Stock Management')

        if role in ['Admin', 'Manager']:
            with st.expander('➕ Add New Stock'):
                c1, c2 = st.columns(2)
                with c1:
                    n = st.text_input('Shoe Name')
                    sz = st.text_input('Size')
                    q = st.number_input('Quantity', min_value=1, value=1)
                with c2:
                    b = st.number_input('Buying Price (KES)', min_value=0.0)
                    sp = st.number_input('Selling Price (KES)', min_value=0.0)
                if st.button('Add to Stock'):
                    if n and sz:
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute("INSERT INTO stock (shoe_name,size,quantity,buying_price,selling_price) VALUES (?,?,?,?,?)",
                                  (n, sz, q, b, sp))
                        conn.commit()
                        conn.close()
                        log_activity(st.session_state.username, 'Add Stock', f'Added {q} pairs of {n}')
                        st.success('Stock added!')
                        st.rerun()
                    else:
                        st.warning('Enter shoe name and size')

        conn = get_conn()
        df = pd.read_sql("SELECT * FROM stock", conn)
        conn.close()
        if df.empty:
            st.info('No stock yet.')
        else:
            st.dataframe(df, use_container_width=True)
            total = (df['quantity'] * df['buying_price']).sum()
            st.metric('Total Stock Value', f'KES {total:,.0f}')

    # ── RECORD SALE ────────────────────────────────────────────────────────────
    elif page == 'Record Sale':
        st.header('🛒 Record a Sale')
        conn = get_conn()
        stock_df = pd.read_sql("SELECT * FROM stock WHERE quantity > 0", conn)
        conn.close()

        if stock_df.empty:
            st.warning('No stock available!')
        else:
            shoe = st.selectbox('Select Shoe', stock_df['shoe_name'].unique())
            shoe_data = stock_df[stock_df['shoe_name'] == shoe]
            size = st.selectbox('Select Size', shoe_data['size'].tolist())
            row = shoe_data[shoe_data['size'] == size].iloc[0]
            max_qty = int(row['quantity'])
            qty = st.number_input('Quantity', min_value=1, max_value=max_qty, value=1)
            price = st.number_input('Selling Price (KES)', min_value=0.0, value=float(row['selling_price']))
            total = qty * price
            st.metric('Total', f'KES {total:,.0f}')
            method = st.selectbox('Payment Method', ['Cash', 'Mpesa', 'Card', 'Credit'])

            if st.button('Record Sale', type='primary'):
                conn = get_conn()
                c = conn.cursor()
                c.execute("INSERT INTO sales (shoe_name,size,quantity,selling_price,total,payment_method,served_by,date) VALUES (?,?,?,?,?,?,?,?)",
                          (shoe, size, qty, price, total, method, st.session_state.username,
                           datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                c.execute("UPDATE stock SET quantity=quantity-? WHERE shoe_name=? AND size=?",
                          (qty, shoe, size))
                conn.commit()
                conn.close()
                log_activity(st.session_state.username, 'Sale', f'Sold {qty} x {shoe} size {size}')
                st.success(f'Sale recorded! Total: KES {total:,.0f}')
                st.rerun()

    # ── EXPENSES ───────────────────────────────────────────────────────────────
    elif page == 'Expenses':
        st.header('💸 Expenses')
        with st.expander('➕ Add Expense'):
            cat = st.selectbox('Category', ['Rent', 'Utilities', 'Transport', 'Marketing', 'Salary', 'Other'])
            desc = st.text_input('Description')
            amt = st.number_input('Amount (KES)', min_value=0.0)
            if st.button('Add Expense'):
                conn = get_conn()
                c = conn.cursor()
                c.execute("INSERT INTO expenses (category,description,amount,date,recorded_by) VALUES (?,?,?,?,?)",
                          (cat, desc, amt, datetime.now().strftime('%Y-%m-%d'), st.session_state.username))
                conn.commit()
                conn.close()
                st.success('Expense recorded!')
                st.rerun()

        conn = get_conn()
        df = pd.read_sql("SELECT * FROM expenses ORDER BY date DESC", conn)
        conn.close()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            st.metric('Total Expenses', f'KES {df["amount"].sum():,.0f}')

    # ── RETURNS ────────────────────────────────────────────────────────────────
    elif page == 'Returns':
        st.header('↩️ Returns')
        with st.expander('➕ Record Return'):
            c1, c2 = st.columns(2)
            with c1:
                sn = st.text_input('Shoe Name')
                sz = st.text_input('Size')
                qty = st.number_input('Quantity', min_value=1, value=1)
            with c2:
                reason = st.text_area('Reason')
                action = st.selectbox('Action', ['Return to Stock', 'Discard', 'Send to Supplier'])
            if st.button('Record Return'):
                if sn:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("INSERT INTO returns (shoe_name,size,quantity,reason,action,date,recorded_by) VALUES (?,?,?,?,?,?,?)",
                              (sn, sz, qty, reason, action, datetime.now().strftime('%Y-%m-%d'), st.session_state.username))
                    if action == 'Return to Stock':
                        c.execute("UPDATE stock SET quantity=quantity+? WHERE shoe_name=? AND size=?",
                                  (qty, sn, sz))
                    conn.commit()
                    conn.close()
                    st.success('Return recorded!')
                    st.rerun()

        conn = get_conn()
        df = pd.read_sql("SELECT * FROM returns ORDER BY date DESC", conn)
        conn.close()
        if not df.empty:
            st.dataframe(df, use_container_width=True)

    # ── SUPPLIERS & CREDIT ─────────────────────────────────────────────────────
    elif page == 'Suppliers & Credit':
        st.header('🏪 Suppliers & Credit')
        tab1, tab2, tab3 = st.tabs(['Suppliers', 'Credit Stock', 'Make Payment'])

        with tab1:
            with st.expander('➕ Add Supplier'):
                c1, c2 = st.columns(2)
                with c1:
                    sname = st.text_input('Supplier Name')
                    sphone = st.text_input('Phone')
                with c2:
                    saddr = st.text_area('Address')
                if st.button('Add Supplier'):
                    if sname:
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute("INSERT INTO suppliers (name,phone,address) VALUES (?,?,?)",
                                  (sname, sphone, saddr))
                        conn.commit()
                        conn.close()
                        st.success('Supplier added!')
                        st.rerun()

            conn = get_conn()
            sup_df = pd.read_sql("SELECT * FROM suppliers", conn)
            conn.close()
            if not sup_df.empty:
                st.dataframe(sup_df, use_container_width=True)

        with tab2:
            conn = get_conn()
            sup_df = pd.read_sql("SELECT * FROM suppliers", conn)
            conn.close()

            if sup_df.empty:
                st.warning('Add a supplier first!')
            else:
                with st.expander('➕ Record Credit Stock'):
                    sup_name = st.selectbox('Supplier', sup_df['name'].tolist())
                    sup_id = int(sup_df[sup_df['name'] == sup_name].iloc[0]['id'])
                    c1, c2 = st.columns(2)
                    with c1:
                        cr_shoe = st.text_input('Shoe Name')
                        cr_qty = st.number_input('Quantity', min_value=1, value=1)
                        cr_amount = st.number_input('Amount Owed (KES)', min_value=0.0)
                    with c2:
                        cr_due = st.date_input('Due Date')
                    if st.button('Record Credit Stock'):
                        if cr_shoe:
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute('''INSERT INTO credit_stock
                                (supplier_id,supplier_name,shoe_name,quantity,amount_owed,amount_paid,due_date,status,date_added)
                                VALUES (?,?,?,?,?,0,?,?,?)''',
                                (sup_id, sup_name, cr_shoe, cr_qty, cr_amount,
                                 str(cr_due), 'Unpaid', datetime.now().strftime('%Y-%m-%d')))
                            conn.commit()
                            conn.close()
                            st.success('Credit stock recorded!')
                            st.rerun()

            conn = get_conn()
            credit_df = pd.read_sql("SELECT * FROM credit_stock ORDER BY due_date", conn)
            conn.close()
            if not credit_df.empty:
                credit_df['remaining'] = credit_df['amount_owed'] - credit_df['amount_paid']
                st.dataframe(credit_df[['supplier_name','shoe_name','quantity','amount_owed','amount_paid','remaining','due_date','status']],
                             use_container_width=True)
                total_owed = credit_df['remaining'].sum()
                st.metric('Total Credit Remaining', f'KES {total_owed:,.0f}')

        with tab3:
            conn = get_conn()
            unpaid = pd.read_sql("SELECT * FROM credit_stock WHERE status != 'Paid'", conn)
            conn.close()
            if unpaid.empty:
                st.info('No outstanding credit!')
            else:
                unpaid['label'] = unpaid['supplier_name'] + ' - ' + unpaid['shoe_name']
                selected = st.selectbox('Select Credit', unpaid['label'].tolist())
                credit_row = unpaid[unpaid['label'] == selected].iloc[0]
                remaining = credit_row['amount_owed'] - credit_row['amount_paid']
                st.metric('Remaining Balance', f'KES {remaining:,.0f}')
                pay_type = st.radio('Payment Type', ['Full Payment', 'Installment'])
                if pay_type == 'Full Payment':
                    pay_amount = remaining
                    st.info(f'Full payment: KES {pay_amount:,.0f}')
                else:
                    pay_amount = st.number_input('Installment Amount (KES)', min_value=1.0, max_value=float(remaining))
                notes = st.text_input('Notes (optional)')

                if st.button('Make Payment', type='primary'):
                    new_paid = credit_row['amount_paid'] + pay_amount
                    new_status = 'Paid' if new_paid >= credit_row['amount_owed'] else 'Partial'
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("UPDATE credit_stock SET amount_paid=?, status=? WHERE id=?",
                              (new_paid, new_status, int(credit_row['id'])))
                    c.execute("INSERT INTO credit_payments (credit_id,amount,payment_date,notes) VALUES (?,?,?,?)",
                              (int(credit_row['id']), pay_amount,
                               datetime.now().strftime('%Y-%m-%d'), notes))
                    conn.commit()
                    conn.close()
                    log_activity(st.session_state.username, 'Credit Payment',
                                 f'Paid KES {pay_amount:,.0f} to {credit_row["supplier_name"]}')
                    st.success(f'Payment of KES {pay_amount:,.0f} recorded!')
                    st.rerun()

    # ── ANALYTICS ──────────────────────────────────────────────────────────────
    elif page == 'Analytics':
        st.header('📈 Analytics')
        conn = get_conn()
        sales_df = pd.read_sql("SELECT * FROM sales", conn)
        stock_df = pd.read_sql("SELECT * FROM stock", conn)
        expenses_df = pd.read_sql("SELECT * FROM expenses", conn)
        conn.close()

        if sales_df.empty:
            st.info('No sales data yet.')
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric('Total Revenue', f'KES {sales_df["total"].sum():,.0f}')
            total_exp = expenses_df['amount'].sum() if not expenses_df.empty else 0
            profit = sales_df['total'].sum() - total_exp
            c2.metric('Estimated Profit', f'KES {profit:,.0f}')
            c3.metric('Total Transactions', len(sales_df))

            st.subheader('Sales by Shoe')
            by_shoe = sales_df.groupby('shoe_name')['total'].sum().reset_index()
            st.bar_chart(by_shoe.set_index('shoe_name'))

            st.subheader('Sales by Payment Method')
            by_method = sales_df.groupby('payment_method')['total'].sum().reset_index()
            st.dataframe(by_method, use_container_width=True)

            st.subheader('Low Stock Alert')
            if not stock_df.empty:
                low = stock_df[stock_df['quantity'] <= 3]
                if not low.empty:
                    st.warning(f'{len(low)} items running low!')
                    st.dataframe(low, use_container_width=True)
                else:
                    st.success('All stock levels are healthy!')

    # ── AI ADVISOR ─────────────────────────────────────────────────────────────
    elif page == 'AI Advisor':
        st.header('🤖 AI Business Advisor')
        st.caption('Ask for business advice based on your SoleTrack data')

        conn = get_conn()
        sales_df = pd.read_sql("SELECT * FROM sales", conn)
        stock_df = pd.read_sql("SELECT * FROM stock", conn)
        expenses_df = pd.read_sql("SELECT * FROM expenses", conn)
        credit_df = pd.read_sql("SELECT * FROM credit_stock WHERE status != 'Paid'", conn)
        conn.close()

        total_sales = sales_df['total'].sum() if not sales_df.empty else 0
        total_exp = expenses_df['amount'].sum() if not expenses_df.empty else 0
        total_stock = len(stock_df) if not stock_df.empty else 0
        total_credit = (credit_df['amount_owed'] - credit_df['amount_paid']).sum() if not credit_df.empty else 0
        top_shoe = sales_df.groupby('shoe_name')['total'].sum().idxmax() if not sales_df.empty else 'N/A'

        context = f"""
You are a business advisor for FMN Shoes, a shoe retail business in Kenya.
Current business data:
- Total Sales Revenue: KES {total_sales:,.0f}
- Total Expenses: KES {total_exp:,.0f}
- Estimated Profit: KES {(total_sales - total_exp):,.0f}
- Stock Items: {total_stock}
- Outstanding Credit to Suppliers: KES {total_credit:,.0f}
- Best Selling Shoe: {top_shoe}

Give practical, specific advice for a small shoe business in Kenya.
Keep answers concise and actionable.
"""
        question = st.text_area('Ask your business question:', 
                                placeholder='e.g. How can I increase my sales? Should I reorder stock?')

        if st.button('Get Advice', type='primary'):
            if question:
                with st.spinner('Thinking...'):
                    try:
                        import urllib.request
                        import json
                        payload = json.dumps({
                            "model": "claude-sonnet-4-20250514",
                            "max_tokens": 1000,
                            "system": context,
                            "messages": [{"role": "user", "content": question}]
                        }).encode()
                        req = urllib.request.Request(
                            "https://api.anthropic.com/v1/messages",
                            data=payload,
                            headers={"Content-Type": "application/json"},
                            method="POST"
                        )
                        with urllib.request.urlopen(req) as resp:
                            data = json.loads(resp.read())
                            answer = data['content'][0]['text']
                            st.info(answer)
                    except Exception as e:
                        # Fallback simple advice
                        st.info(f"""Based on your data:
- Revenue: KES {total_sales:,.0f} | Expenses: KES {total_exp:,.0f}
- Profit margin: {((total_sales-total_exp)/total_sales*100) if total_sales > 0 else 0:.1f}%
- Best seller: {top_shoe}

**Advice:** Focus on restocking {top_shoe} as it's your top earner. 
Reduce credit exposure (KES {total_credit:,.0f} outstanding). 
Consider Mpesa payments to improve cash flow tracking.""")
            else:
                st.warning('Please enter a question')

    # ── USER MANAGEMENT ────────────────────────────────────────────────────────
    elif page == 'User Management':
        st.header('👥 User Management')
        with st.expander('➕ Add New User'):
            c1, c2 = st.columns(2)
            with c1:
                new_user = st.text_input('Username')
                new_name = st.text_input('Full Name')
                new_phone = st.text_input('Phone')
            with c2:
                new_pass = st.text_input('Password', type='password')
                new_role = st.selectbox('Role', ['Admin', 'Manager', 'Cashier', 'Salesperson'])
            if st.button('Add User'):
                if new_user and new_pass and new_name:
                    conn = get_conn()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO users (username,password,role,full_name,phone) VALUES (?,?,?,?,?)",
                                  (new_user, hash_password(new_pass), new_role, new_name, new_phone))
                        conn.commit()
                        st.success(f'User {new_user} added!')
                        log_activity(st.session_state.username, 'Add User', f'Added {new_user}')
                    except:
                        st.error('Username already exists!')
                    conn.close()
                    st.rerun()

        conn = get_conn()
        users_df = pd.read_sql("SELECT id,username,role,full_name,phone,is_active,last_login FROM users", conn)
        conn.close()
        st.dataframe(users_df, use_container_width=True)

        st.subheader('Reset User Password')
        conn = get_conn()
        users_df2 = pd.read_sql("SELECT username FROM users", conn)
        conn.close()
        reset_user = st.selectbox('Select User', users_df2['username'].tolist())
        new_pwd = st.text_input('New Password', type='password')
        if st.button('Reset Password'):
            if new_pwd:
                conn = get_conn()
                c = conn.cursor()
                c.execute("UPDATE users SET password=?, failed_attempts=0 WHERE username=?",
                          (hash_password(new_pwd), reset_user))
                conn.commit()
                conn.close()
                st.success(f'Password reset for {reset_user}')

    # ── ACTIVITY LOG ───────────────────────────────────────────────────────────
    elif page == 'Activity Log':
        st.header('📋 Activity Log')
        conn = get_conn()
        df = pd.read_sql("SELECT * FROM activity_log ORDER BY date DESC LIMIT 200", conn)
        conn.close()
        if df.empty:
            st.info('No activity yet.')
        else:
            st.dataframe(df, use_container_width=True)

    # ── CHANGE PASSWORD ────────────────────────────────────────────────────────
    elif page == 'Change Password':
        st.header('🔑 Change Password')
        old_pwd = st.text_input('Current Password', type='password')
        new_pwd = st.text_input('New Password', type='password')
        confirm_pwd = st.text_input('Confirm New Password', type='password')
        if st.button('Change Password', type='primary'):
            if new_pwd != confirm_pwd:
                st.error('New passwords do not match!')
            else:
                conn = get_conn()
                user = pd.read_sql("SELECT * FROM users WHERE username=?", conn,
                                   params=(st.session_state.username,))
                conn.close()
                if verify_password(old_pwd, user.iloc[0]['password']):
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("UPDATE users SET password=? WHERE username=?",
                              (hash_password(new_pwd), st.session_state.username))
                    conn.commit()
                    conn.close()
                    st.success('Password changed successfully!')
                    log_activity(st.session_state.username, 'Change Password', 'Password updated')
                else:
                    st.error('Current password is incorrect!')
