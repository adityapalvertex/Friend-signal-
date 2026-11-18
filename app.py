import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "friend_signal.db"

st.set_page_config(
    page_title="FRIEND SIGNAL",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
.block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
[data-testid="stAppViewContainer"] {background: #0b1020;}
[data-testid="stSidebar"] {background: #10182b;}
.hero {
  padding: 28px 30px; border: 1px solid #263858; border-radius: 22px;
  background: linear-gradient(120deg,#152849,#10182b 65%,#17213b);
  margin-bottom: 22px;
}
.hero h1 {font-size: 2.25rem; margin: 0; color: #f4f7ff;}
.hero p {color: #b8c8e6; margin: 8px 0 0 0;}
.eyebrow {color:#73b7ff; font-weight:700; letter-spacing:.14em; font-size:.75rem;}
.card {
  border: 1px solid #263858; border-radius: 16px; padding: 18px 20px;
  background: #111b30; margin: 10px 0;
}
.muted {color:#9aabc8; font-size:.9rem;}
.pill {display:inline-block; border-radius:999px; padding:4px 10px;
  background:#1b3659; color:#9fd0ff; font-size:.78rem; font-weight:600;}
div.stButton > button, div.stFormSubmitButton > button {
  border-radius: 10px; font-weight: 650; min-height: 2.6rem;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def columns(con, table):
    return {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}


def initialize():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            bio TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS friendships (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            friend_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY(user_id, friend_id),
            CHECK(user_id <> friend_id)
        );
        CREATE TABLE IF NOT EXISTS friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending'
              CHECK(status IN ('pending','accepted','rejected')),
            created_at TEXT NOT NULL,
            UNIQUE(sender_id, receiver_id),
            CHECK(sender_id <> receiver_id)
        );
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recommendation_id INTEGER NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
            is_read INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0,1)),
            created_at TEXT NOT NULL,
            UNIQUE(recipient_id, recommendation_id)
        );
        CREATE INDEX IF NOT EXISTS idx_recommendations_sender
          ON recommendations(sender_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_recipient
          ON notifications(recipient_id, is_read);
        """)
        # Add missing columns when opening a database created by an earlier prototype.
        if "bio" not in columns(con, "users"):
            con.execute("ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''")
        if "created_at" not in columns(con, "friendships"):
            con.execute("ALTER TABLE friendships ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        # Seed only when the database is empty; never overwrite existing user data.
        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            now = datetime.now().isoformat(timespec="seconds")
            con.executemany(
                "INSERT INTO users(name,bio,created_at) VALUES(?,?,?)",
                [
                    ("Aditya", "Discover good things through people you trust.", now),
                    ("Aarav", "Always finding interesting videos and ideas.", now),
                    ("Diya", "Curious about places, tech and creativity.", now),
                    ("Kabir", "Sharing useful things with friends.", now),
                ],
            )
            ids = {r["name"]: r["id"] for r in con.execute("SELECT id,name FROM users")}
            # Demo network: Aditya-Aarav-Diya are connected; Kabir is separate.
            for a, b in [("Aditya", "Aarav"), ("Aditya", "Diya"), ("Aarav", "Diya")]:
                add_friendship(con, ids[a], ids[b], now)


def add_friendship(con, a, b, now=None):
    now = now or datetime.now().isoformat(timespec="seconds")
    con.execute(
        "INSERT OR IGNORE INTO friendships(user_id,friend_id,created_at) VALUES(?,?,?)",
        (a, b, now),
    )
    con.execute(
        "INSERT OR IGNORE INTO friendships(user_id,friend_id,created_at) VALUES(?,?,?)",
        (b, a, now),
    )


def are_mutual_friends(con, a, b):
    row = con.execute("""
        SELECT EXISTS(
          SELECT 1 FROM friendships f1
          JOIN friendships f2
            ON f2.user_id=f1.friend_id AND f2.friend_id=f1.user_id
          WHERE f1.user_id=? AND f1.friend_id=?
        )
    """, (a, b)).fetchone()
    return bool(row[0])


def mutual_friend_ids(con, user_id):
    return [
        r["friend_id"] for r in con.execute("""
            SELECT f1.friend_id
            FROM friendships f1
            JOIN friendships f2
              ON f2.user_id=f1.friend_id AND f2.friend_id=f1.user_id
            WHERE f1.user_id=?
        """, (user_id,))
    ]


def valid_http_url(value):
    try:
        p = urlparse(value.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def get_users():
    with db() as con:
        return con.execute("SELECT id,name,bio FROM users ORDER BY name COLLATE NOCASE").fetchall()


def notify_recommendation(con, sender_id, rec_id, now):
    for recipient_id in mutual_friend_ids(con, sender_id):
        con.execute("""
            INSERT OR IGNORE INTO notifications
              (recipient_id,sender_id,recommendation_id,is_read,created_at)
            VALUES(?,?,?,0,?)
        """, (recipient_id, sender_id, rec_id, now))


def header():
    st.markdown("""
    <div class="hero">
      <div class="eyebrow">YOUR CIRCLE. YOUR DISCOVERIES.</div>
      <h1>FRIEND SIGNAL <span style="color:#69b5ff">●</span></h1>
      <p>Good content travels further when it comes from people you know.</p>
    </div>
    """, unsafe_allow_html=True)


initialize()
users = get_users()
if not users:
    st.error("No user profiles are available.")
    st.stop()

user_map = {r["name"]: r["id"] for r in users}
with st.sidebar:
    st.markdown("## 🔵 FRIEND SIGNAL")
    st.caption("Local MVP · Demo mode")
    selected_name = st.selectbox(
        "Preview as",
        list(user_map.keys()),
        index=list(user_map.keys()).index("Aditya") if "Aditya" in user_map else 0,
    )
    current_id = user_map[selected_name]
    st.success(f"Viewing as {selected_name}")
    st.caption("Demo profile switcher — this is not real login.")
    st.divider()
    st.caption("Built as a local prototype with Python + SQLite.")

with db() as con:
    unread_count = con.execute("""
        SELECT COUNT(*) FROM notifications n
        WHERE n.recipient_id=? AND n.is_read=0
          AND EXISTS (
            SELECT 1 FROM friendships f1
            JOIN friendships f2
              ON f2.user_id=f1.friend_id AND f2.friend_id=f1.user_id
            WHERE f1.user_id=n.recipient_id AND f1.friend_id=n.sender_id
          )
    """, (current_id,)).fetchone()[0]

header()
st.markdown(
    f'<span class="pill">SIGNED IN AS {selected_name.upper()}</span> '
    f'<span class="pill">🔔 {unread_count} UNREAD</span>',
    unsafe_allow_html=True,
)

feed_tab, recommend_tab, friends_tab, notifications_tab, profile_tab = st.tabs([
    "🏠 Feed", "📡 Recommend", "👥 Friends", "🔔 Notifications", "👤 Profile"
])

# FEED
with feed_tab:
    st.subheader("Recommended by your friends")
    st.caption("Content shared by people who are mutually connected with you.")
    with db() as con:
        feed = con.execute("""
            WITH visible AS (
              SELECT r.id,r.sender_id,r.title,r.url,r.note,r.created_at,u.name sender_name
              FROM recommendations r
              JOIN users u ON u.id=r.sender_id
              JOIN friendships f1 ON f1.user_id=? AND f1.friend_id=r.sender_id
              JOIN friendships f2 ON f2.user_id=r.sender_id AND f2.friend_id=?
            ),
            grouped AS (
              SELECT TRIM(url) content_key,
                     COUNT(DISTINCT sender_id) friend_count,
                     GROUP_CONCAT(DISTINCT sender_name) recommenders,
                     MAX(id) latest_id
              FROM visible GROUP BY TRIM(url)
            )
            SELECT v.*,g.friend_count,g.recommenders
            FROM grouped g JOIN visible v ON v.id=g.latest_id
            ORDER BY g.friend_count DESC,g.latest_id DESC
        """, (current_id, current_id)).fetchall()
    if not feed:
        st.info("Your feed is quiet. Recommend something or connect with friends to get started.")
    for item in feed:
        with st.container(border=True):
            st.markdown(f"**{item['title']}**")
            st.markdown(
                f'<span class="pill">🔥 {item["friend_count"]} friend(s) recommended</span>',
                unsafe_allow_html=True,
            )
            st.write("👥 " + (item["recommenders"] or "Friend"))
            if item["note"]:
                st.write(item["note"])
            st.link_button("Open content ↗", item["url"], key=f"feed_open_{item['latest_id']}")
            st.caption(f"Latest recommendation · {item['created_at']}")

# RECOMMEND
with recommend_tab:
    st.subheader("Recommend something")
    st.write("Share a link with your mutual friends. Your name stays attached to the recommendation.")
    with st.form("recommend_form", clear_on_submit=True):
        title = st.text_input("Title", placeholder="e.g. A brilliant science video")
        url = st.text_input("Content URL", placeholder="https://...")
        note = st.text_area("Why are you recommending it? (optional)", max_chars=500)
        submit = st.form_submit_button("📡 Recommend to my friends", use_container_width=True)
    if submit:
        if not title.strip():
            st.error("Please enter a title.")
        elif not valid_http_url(url):
            st.error("Enter a complete link beginning with http:// or https://.")
        else:
            now = datetime.now().isoformat(timespec="seconds")
            with db() as con:
                cur = con.execute("""
                    INSERT INTO recommendations(sender_id,title,url,note,created_at)
                    VALUES(?,?,?,?,?)
                """, (current_id, title.strip(), url.strip(), note.strip(), now))
                notify_recommendation(con, current_id, cur.lastrowid, now)
                recipients = len(mutual_friend_ids(con, current_id))
            st.success(f"Recommendation published. {recipients} mutual friend(s) notified.")
            st.rerun()
    with db() as con:
        own = con.execute("""
            SELECT title,url,created_at FROM recommendations
            WHERE sender_id=? ORDER BY id DESC LIMIT 5
        """, (current_id,)).fetchall()
    if own:
        st.divider()
        st.markdown("#### Your recent recommendations")
        for r in own:
            st.write(f"**{r['title']}** · {r['created_at']}")
            st.caption(r["url"])

# FRIENDS
with friends_tab:
    find_col, list_col = st.columns([1, 1])
    with find_col:
        st.subheader("Find people")
        all_users = get_users()
        with db() as con:
            current_friends = set(mutual_friend_ids(con, current_id))
            pending_out = {
                r["receiver_id"] for r in con.execute("""
                    SELECT receiver_id FROM friend_requests
                    WHERE sender_id=? AND status='pending'
                """, (current_id,))
            }
            pending_in = {
                r["sender_id"] for r in con.execute("""
                    SELECT sender_id FROM friend_requests
                    WHERE receiver_id=? AND status='pending'
                """, (current_id,))
            }
        candidates = [
            r for r in all_users
            if r["id"] != current_id
            and r["id"] not in current_friends
            and r["id"] not in pending_out
            and r["id"] not in pending_in
        ]
        if candidates:
            with st.form("friend_request_form"):
                candidate_name = st.selectbox("Choose a person", [r["name"] for r in candidates])
                send_req = st.form_submit_button("Send friend request", use_container_width=True)
            if send_req:
                target_id = next(r["id"] for r in candidates if r["name"] == candidate_name)
                now = datetime.now().isoformat(timespec="seconds")
                with db() as con:
                    reverse = con.execute("""
                        SELECT id FROM friend_requests
                        WHERE sender_id=? AND receiver_id=? AND status='pending'
                    """, (target_id, current_id)).fetchone()
                    if reverse:
                        st.info("They have already requested you. Accept their request on the right.")
                    else:
                        existing = con.execute("""
                            SELECT id,status FROM friend_requests
                            WHERE sender_id=? AND receiver_id=?
                        """, (current_id, target_id)).fetchone()
                        if existing:
                            con.execute("""
                                UPDATE friend_requests SET status='pending',created_at=?
                                WHERE id=?
                            """, (now, existing["id"]))
                        else:
                            con.execute("""
                                INSERT INTO friend_requests(sender_id,receiver_id,status,created_at)
                                VALUES(?,?,'pending',?)
                            """, (current_id, target_id, now))
                st.rerun()
        else:
            st.info("No new people to connect with right now.")
    with list_col:
        st.subheader("Your connections")
        with db() as con:
            friends = con.execute("""
                SELECT u.id,u.name FROM friendships f
                JOIN users u ON u.id=f.friend_id
                WHERE f.user_id=? ORDER BY u.name
            """, (current_id,)).fetchall()
        if not friends:
            st.info("No friends yet.")
        for friend in friends:
            with st.container(border=True):
                st.write(f"🟢 **{friend['name']}**")
                if st.button("Remove friend", key=f"remove_{friend['id']}"):
                    with db() as con:
                        con.execute("""
                            DELETE FROM friendships
                            WHERE (user_id=? AND friend_id=?)
                               OR (user_id=? AND friend_id=?)
                        """, (current_id, friend["id"], friend["id"], current_id))
                        con.execute("""
                            DELETE FROM friend_requests
                            WHERE (sender_id=? AND receiver_id=?)
                               OR (sender_id=? AND receiver_id=?)
                        """, (current_id, friend["id"], friend["id"], current_id))
                    st.success("Friend removed. Their content is no longer visible in your friends-only feed.")
                    st.rerun()

    st.divider()
    incoming_col, outgoing_col = st.columns(2)
    with incoming_col:
        st.subheader("Incoming requests")
        with db() as con:
            incoming = con.execute("""
                SELECT fr.id,fr.sender_id,u.name
                FROM friend_requests fr JOIN users u ON u.id=fr.sender_id
                WHERE fr.receiver_id=? AND fr.status='pending'
                ORDER BY fr.id DESC
            """, (current_id,)).fetchall()
        if not incoming:
            st.caption("No pending requests.")
        for req in incoming:
            with st.container(border=True):
                st.write(f"**{req['name']}** wants to connect.")
                ac, rj = st.columns(2)
                if ac.button("Accept", key=f"accept_{req['id']}"):
                    now = datetime.now().isoformat(timespec="seconds")
                    with db() as con:
                        valid = con.execute("""
                            SELECT sender_id FROM friend_requests
                            WHERE id=? AND receiver_id=? AND status='pending'
                        """, (req["id"], current_id)).fetchone()
                        if valid:
                            add_friendship(con, current_id, valid["sender_id"], now)
                            con.execute("UPDATE friend_requests SET status='accepted' WHERE id=?", (req["id"],))
                    st.rerun()
                if rj.button("Reject", key=f"reject_{req['id']}"):
                    with db() as con:
                        con.execute("""
                            UPDATE friend_requests SET status='rejected'
                            WHERE id=? AND receiver_id=? AND status='pending'
                        """, (req["id"], current_id))
                    st.rerun()
    with outgoing_col:
        st.subheader("Sent requests")
        with db() as con:
            outgoing = con.execute("""
                SELECT u.name,fr.created_at FROM friend_requests fr
                JOIN users u ON u.id=fr.receiver_id
                WHERE fr.sender_id=? AND fr.status='pending'
                ORDER BY fr.id DESC
            """, (current_id,)).fetchall()
        if not outgoing:
            st.caption("No pending sent requests.")
        for req in outgoing:
            st.write(f"🕒 Waiting for **{req['name']}**")

# NOTIFICATIONS
with notifications_tab:
    st.subheader("Notifications")
    with db() as con:
        notifications = con.execute("""
            SELECT n.id,n.is_read,n.created_at,u.name sender,r.title,r.url,r.note
            FROM notifications n
            JOIN users u ON u.id=n.sender_id
            JOIN recommendations r ON r.id=n.recommendation_id
            WHERE n.recipient_id=?
              AND EXISTS (
                SELECT 1 FROM friendships f1
                JOIN friendships f2
                  ON f2.user_id=f1.friend_id AND f2.friend_id=f1.user_id
                WHERE f1.user_id=n.recipient_id AND f1.friend_id=n.sender_id
              )
            ORDER BY n.id DESC
        """, (current_id,)).fetchall()
    unread = sum(1 for n in notifications if n["is_read"] == 0)
    a, b = st.columns(2)
    a.metric("Total notifications", len(notifications))
    b.metric("Unread", unread)
    if unread and st.button("Mark all as read"):
        with db() as con:
            con.execute("""
                UPDATE notifications SET is_read=1
                WHERE recipient_id=? AND is_read=0
                  AND EXISTS (
                    SELECT 1 FROM friendships f1
                    JOIN friendships f2
                      ON f2.user_id=f1.friend_id AND f2.friend_id=f1.user_id
                    WHERE f1.user_id=notifications.recipient_id
                      AND f1.friend_id=notifications.sender_id
                  )
            """, (current_id,))
        st.rerun()
    if not notifications:
        st.info("Nothing here yet. Recommendations from your friends will appear here.")
    for n in notifications:
        with st.container(border=True):
            st.caption("🆕 NEW" if not n["is_read"] else "✓ READ")
            st.write(f"**{n['sender']}** recommended **{n['title']}**")
            if n["note"]:
                st.write(n["note"])
            left, right = st.columns([1, 1])
            left.link_button("Open content ↗", n["url"], key=f"notif_link_{n['id']}")
            if not n["is_read"] and right.button("Mark as read", key=f"mark_{n['id']}"):
                with db() as con:
                    con.execute("""
                        UPDATE notifications SET is_read=1
                        WHERE id=? AND recipient_id=?
                    """, (n["id"], current_id))
                st.rerun()
            st.caption(n["created_at"])

# PROFILE
with profile_tab:
    with db() as con:
        me = con.execute("SELECT name,bio,created_at FROM users WHERE id=?", (current_id,)).fetchone()
        shared = con.execute("SELECT COUNT(*) FROM recommendations WHERE sender_id=?", (current_id,)).fetchone()[0]
        friends_count = len(mutual_friend_ids(con, current_id))
        received = con.execute("""
            SELECT COUNT(DISTINCT r.id) FROM recommendations r
            WHERE EXISTS (
              SELECT 1 FROM friendships f1
              JOIN friendships f2 ON f2.user_id=f1.friend_id AND f2.friend_id=f1.user_id
              WHERE f1.user_id=? AND f1.friend_id=r.sender_id
            )
        """, (current_id,)).fetchone()[0]
        recent = con.execute("""
            SELECT r.title,r.created_at,u.name sender
            FROM recommendations r JOIN users u ON u.id=r.sender_id
            WHERE EXISTS (
              SELECT 1 FROM friendships f1
              JOIN friendships f2 ON f2.user_id=f1.friend_id AND f2.friend_id=f1.user_id
              WHERE f1.user_id=? AND f1.friend_id=r.sender_id
            )
            ORDER BY r.id DESC LIMIT 5
        """, (current_id,)).fetchall()
    st.subheader(f"👤 {me['name']}")
    st.caption(me["bio"] or "A FRIEND SIGNAL member.")
    c1,c2,c3 = st.columns(3)
    c1.metric("Shared", shared)
    c2.metric("Received", received)
    c3.metric("Friends", friends_count)
    st.divider()
    st.markdown("#### Recent activity from your friends")
    if recent:
        for r in recent:
            st.write(f"**{r['sender']}** recommended **{r['title']}**")
            st.caption(r["created_at"])
    else:
        st.info("Your friends' activity will appear here.")
    st.divider()
    st.caption("FRIEND SIGNAL · Discover together.")

st.divider()
st.caption("FRIEND SIGNAL local MVP · Data is stored in friend_signal.db beside app.py.")
