import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import random
from plugin.priority_engine import calculate_distance, calculate_risk, classify_request

DB_NAME = "database.db"

# ----------------- DB Setup -----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT, receiver TEXT, category TEXT,
            urgency INTEGER, impact INTEGER,
            sender_lat REAL, sender_lon REAL, receiver_lat REAL, receiver_lon REAL,
            distance REAL, risk_score REAL, priority TEXT, final_priority TEXT,
            decision TEXT, override_reason TEXT, status TEXT,
            rating REAL, feedback_count INTEGER, timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()
init_db()

# ----------------- Admin -----------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"

# ----------------- Session -----------------
if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if "otp_verified" not in st.session_state: st.session_state.otp_verified = False
if "otp_code" not in st.session_state: st.session_state.otp_code = ""
if "override_trigger" not in st.session_state: st.session_state.override_trigger = {}

# ----------------- Helper Functions -----------------
def compute_urgency_impact(category, acceptable_delay, distance, people, vulnerability):
    urgency, impact = 1,1
    if category.lower() in ["medicine","blood"]: urgency+=4; impact+=3
    if vulnerability.lower() in ["child","elderly","disabled"]: urgency+=2; impact+=2
    impact += min(people,5)
    if acceptable_delay<30: urgency+=2
    urgency -= distance/20
    return max(1,min(10,int(urgency))), max(1,min(10,int(impact)))

def place_order(sender, receiver, category, acceptable_delay, people, vulnerability, resources=1.0):
    sender_lat,sender_lon=12.9716,77.5946
    receiver_lat,receiver_lon=13.0827,80.2707
    distance = calculate_distance(sender_lat,sender_lon,receiver_lat,receiver_lon)
    urgency,impact=compute_urgency_impact(category,acceptable_delay,distance,people,vulnerability)
    risk_score = calculate_risk(urgency,impact,category,distance,people,vulnerability,resources)
    priority,decision = classify_request(risk_score)
    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn=get_db(); cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO requests (
            sender, receiver, category, urgency, impact,
            sender_lat, sender_lon, receiver_lat, receiver_lon,
            distance, risk_score, priority, final_priority,
            decision, status, rating, feedback_count, timestamp
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,(sender,receiver,category,urgency,impact,sender_lat,sender_lon,
        receiver_lat,receiver_lon,distance,risk_score,priority,priority,decision,
        "Order Placed",None,0,timestamp))
    conn.commit(); conn.close()
    st.success(f"Order placed! Risk: {risk_score}, Priority: {priority}")

def update_override(req_id,new_priority,reason):
    conn=get_db(); cursor=conn.cursor()
    cursor.execute("UPDATE requests SET final_priority=?, override_reason=? WHERE id=?",(new_priority,reason,req_id))
    conn.commit(); conn.close()

def simulate_status():
    conn=get_db(); cursor=conn.cursor()
    cursor.execute("SELECT * FROM requests"); rows=cursor.fetchall()
    for r in rows:
        if r["status"]=="Order Placed": cursor.execute("UPDATE requests SET status='Picked Up' WHERE id=?",(r["id"],))
        elif r["status"]=="Picked Up": cursor.execute("UPDATE requests SET status='In Transit' WHERE id=?",(r["id"],))
        elif r["status"]=="In Transit": cursor.execute("UPDATE requests SET status='Delivered' WHERE id=?",(r["id"],))
    conn.commit(); conn.close()

def collect_feedback(req_id,rating):
    conn=get_db(); cursor=conn.cursor()
    cursor.execute("SELECT rating, feedback_count FROM requests WHERE id=?",(req_id,))
    row=cursor.fetchone()
    if row["feedback_count"]==0 or row["rating"] is None: new_rating=rating
    else: new_rating=(row["rating"]*row["feedback_count"]+rating)/(row["feedback_count"]+1)
    new_count=row["feedback_count"]+1
    cursor.execute("UPDATE requests SET rating=?, feedback_count=? WHERE id=?",(new_rating,new_count,req_id))
    conn.commit(); conn.close()

# ----------------- Streamlit UI -----------------
st.set_page_config(page_title="Priority Delivery System", layout="wide")
menu=["Home","Place Order","Track Order","Admin Login"]
choice=st.sidebar.selectbox("Navigation",menu)

# --------- Home ---------
if choice=="Home":
    st.markdown("<h1 style='text-align:center;color:#FFFDD0;'>Priority Delivery System</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>AI-driven prioritized delivery with human-in-loop override and feedback learning.</p>", unsafe_allow_html=True)

# --------- Place Order ---------
elif choice=="Place Order":
    st.subheader("Place a New Order")
    with st.form("order_form"):
        sender=st.text_input("Sender Name")
        receiver=st.text_input("Receiver Name")
        category=st.selectbox("Item Category", ["Medicine","Blood","Security","Infrastructure","General"])
        people=st.number_input("People Affected",1,50,1)
        vulnerability=st.selectbox("Vulnerability",["Normal","Child","Elderly","Disabled"])
        acceptable_delay=st.number_input("Acceptable Delay (minutes)",1,120,30)
        resources=st.slider("Available Resources",0.5,1.0,1.0,0.05)
        submit=st.form_submit_button("Place Order")
    if submit: place_order(sender,receiver,category,acceptable_delay,people,vulnerability,resources)

# --------- Track Order ---------
elif choice=="Track Order":
    st.subheader("Track Orders")
    simulate_status()
    conn=get_db(); df=pd.read_sql("SELECT * FROM requests ORDER BY timestamp DESC",conn)
    st.dataframe(df[['id','sender','receiver','category','risk_score','priority','final_priority','status']])
    delivered=df[df['status']=="Delivered"]
    for idx,row in delivered.iterrows():
        rating=st.slider(f"Rate delivery impact for Order {row['id']}",1,5,3,key=f"rating_{row['id']}")
        submit_feedback=st.button(f"Submit Feedback for Order {row['id']}",key=f"fb_{row['id']}")
        if submit_feedback: collect_feedback(row['id'],rating); st.success(f"Feedback submitted for Order {row['id']}")

# --------- Admin Login ---------
elif choice == "Admin Login":
    st.subheader("Admin Login")

    # Step 1: Not logged in → ask for credentials
    if not st.session_state.get("admin_logged_in", False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.session_state.otp_verified = False
                st.session_state.otp_code = random.randint(100000, 999999)
                st.success("Login successful! OTP generated below (demo).")
                with st.expander("Simulated OTP"):
                    st.code(st.session_state.otp_code)
            else:
                st.error("Invalid credentials")
        st.stop()  # stop execution until next interaction

    # Step 2: Logged in but OTP not verified → ask for OTP
    elif st.session_state.get("admin_logged_in") and not st.session_state.get("otp_verified"):
        otp_input = st.text_input("Enter OTP here")
        if st.button("Verify OTP"):
            if str(otp_input) == str(st.session_state.otp_code):
                st.session_state.otp_verified = True
                st.success("OTP verified! Welcome Admin.")
            else:
                st.error("Invalid OTP")
        st.stop()  # stop execution until next interaction

    # Step 3: OTP verified → show admin panel
    else:
        st.subheader("Admin Panel")

        conn = get_db()
        df = pd.read_sql("SELECT * FROM requests ORDER BY risk_score DESC", conn)

        if st.button("View Priority Queue"):
            st.markdown("### Full Priority Queue")
            st.dataframe(df[['id','sender','receiver','category','risk_score','priority','final_priority','status']])

        # Filter MEDIUM priority for override
        medium_df = df[df['priority'] == "MEDIUM"]
        if not medium_df.empty:
            st.markdown("### Medium Priority Override")
            for idx, row in medium_df.iterrows():
                st.markdown(f"**Order ID {row['id']}** | Sender: {row['sender']} | Receiver: {row['receiver']} | AI Priority: {row['priority']}")
                
                override_toggle = st.checkbox("Override?", key=f"toggle_{row['id']}")
                if override_toggle:
                    new_priority = st.selectbox(
                        "Set New Priority",
                        ["HIGH", "MEDIUM", "LOW"],
                        index=["HIGH", "MEDIUM", "LOW"].index(row['final_priority']),
                        key=f"priority_{row['id']}"
                    )
                    reason = st.text_input("Reason for override", key=f"reason_{row['id']}")
                    
                    if st.button(f"Update Order {row['id']}", key=f"btn_{row['id']}"):
                        update_override(row['id'], new_priority, reason)
                        st.success(f"Order {row['id']} updated!")
                        st.session_state.override_trigger[row['id']] = True  # optional UI refresh

        conn.close()