# FRIEND SIGNAL — Ready-to-run local MVP

A local Python + Streamlit + SQLite prototype for social recommendations between friends.

## Included
- Demo profiles and profile switching
- Friend requests: send, accept, reject
- Reciprocal friendships
- Friends-only recommendation feed
- Recommend a URL with title and note
- Notifications with unread/read state
- Combined recommendations when multiple friends recommend the same URL
- Remove friend
- Profile statistics and recent friend activity
- SQLite database created automatically

## Requirements
- Python 3.10+
- Internet connection only for installing Streamlit (the app itself runs locally)

## Windows setup
1. Extract this ZIP.
2. Open the extracted `friend_signal_ready` folder in VS Code.
3. Open Terminal in that folder.
4. Run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app.py
```

If PowerShell blocks activation, run Streamlit directly:
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

Or double-click `run_windows.bat`.

## First demo
The first launch creates four sample users:
- Aditya
- Aarav
- Diya
- Kabir

Demo network:
- Aditya ↔ Aarav
- Aditya ↔ Diya
- Aarav ↔ Diya
- Kabir is initially unconnected

Use the **Preview as** selector in the sidebar to test different accounts.
Example: switch to Aditya and recommend a link; switch to Diya to see the feed and notification. Kabir should not see Aditya's recommendation until they become friends.

## Data
The app creates `friend_signal.db` in the same folder. Keep it beside `app.py`.
To reset the demo database, close the app and delete `friend_signal.db`; the next launch recreates the sample data. This permanently deletes local demo activity.

## Important limitations
This is a **local demonstration MVP**, not a public production service:
- Profile switching is a demo account selector, not authentication.
- There is no password/login system or account recovery.
- SQLite is suitable for this local prototype, not concurrent public hosting.
- Do not put real private information or invite public users yet.
- Before public launch, implement real authentication, server-side authorization, abuse reporting/moderation, rate limits, secure deployment, backups, and privacy/legal review.
- Notifications are in-app only, not Android push notifications.

The app uses parameterized SQL queries for user input and checks reciprocal friendship relationships before showing recommendations.
