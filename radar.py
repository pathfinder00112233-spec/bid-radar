import os
import time
import imaplib
from datetime import datetime
from email.message import EmailMessage
import requests

TRADE_CONFIG = {
    "Roofing & Waterproofing": {
        "search_query": "roofing OR roof OR waterproofing",
        "keywords": ["roof", "roofing", "tpo", "epdm", "waterproofing", "membrane"],
        "recipients": ["info@mrtpo.com", "info@empireroofing.com"],
        "intro": (
            "Hey team,\n\n"
            "Our radar picked up these active federal commercial roofing solicitations "
            "in your territory this morning. Key scopes and links are organized below:\n\n"
        )
    },
    "HVAC & Mechanical": {
        "search_query": "HVAC OR chiller OR boiler OR mechanical",
        "keywords": ["hvac", "mechanical", "chiller", "boiler", "air handler", "ventilation", "duct"],
        "recipients": ["info@acrepairsatx.com"],
        "intro": (
            "Hey team,\n\n"
            "Our radar captured these fresh federal commercial HVAC & mechanical opportunities "
            "in your territory today. Distilled scopes and links are below:\n\n"
        )
    },
    "Electrical Systems": {
        "search_query": "electrical OR switchgear OR generator OR transformer",
        "keywords": ["electrical", "switchgear", "generator", "transformer", "wiring", "panelboard"],
        "recipients": ["service@absolute-pwr.com"],
        "intro": (
            "Hey team,\n\n"
            "Our radar flagged these active federal commercial electrical solicitations "
            "in your territory. Key scopes and submission details are organized below:\n\n"
        )
    },
    "Paving & Asphalt": {
        "search_query": "paving OR asphalt OR concrete OR sealcoat",
        "keywords": ["paving", "asphalt", "sealcoat", "striping", "resurfacing", "parking lot", "concrete"],
        "recipients": ["chriss@pavecon.com"],
        "intro": (
            "Hey team,\n\n"
            "Our radar identified these active federal paving and surface solicitations. "
            "Distilled details and points of contact are listed below:\n\n"
        )
    },
    "Painting & Protective Coatings": {
        "search_query": "painting OR coatings OR sandblast",
        "keywords": ["painting", "protective coating", "industrial paint", "sandblast", "coatings"],
        "recipients": ["spartanpaintingsa@gmail.com"],
        "intro": (
            "Hey team,\n\n"
            "Our radar identified these active federal commercial painting and coating opportunities. "
            "Summarized scopes and contacts are below for your estimating desk:\n\n"
        )
    }
}

SENT_TRACKER_FILE = "sent_leads.txt"
PITCH_SIGNATURE = (
    "\n\n---\n"
    "We track active SAM.gov solicitations daily for commercial estimators.\n"
    "Daily Bid Radar: $499/year (zero web portals, straight to mobile inbox).\n"
    "Reply 'START' to add your estimating team to our daily feed."
)

def load_sent_ids():
    if not os.path.exists(SENT_TRACKER_FILE):
        return set()
    with open(SENT_TRACKER_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}

def save_sent_ids(new_ids):
    with open(SENT_TRACKER_FILE, "a", encoding="utf-8") as f:
        for nid in new_ids:
            f.write(f"{nid}\n")

def fetch_trade_opportunities(query_text):
    url = "https://sam.gov/api/prod/sgs/v1/search/"
    params = {
        "index": "_all",
        "q": query_text,
        "page": 0,
        "size": 15,
        "sort": "-modifiedDate",
        "mode": "search",
        "is_active": "true"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }
    
    bids = []
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        if resp.status_code == 200:
            results = resp.json().get("_embedded", {}).get("results", [])
            for r in results:
                desc = r.get("description") or r.get("title") or "Commercial scope specified in solicitation."
                deadline = r.get("responseDate", "Check solicitation link")
                if "T" in str(deadline):
                    deadline = str(deadline).split("T")[0]

                bids.append({
                    "noticeId": str(r.get("_id", time.time())),
                    "title": r.get("title", "Federal Solicitation"),
                    "solicitationNumber": r.get("solicitationNumber", "N/A"),
                    "department": r.get("organizationHierarchy", [{}])[0].get("name", "Federal Agency") if r.get("organizationHierarchy") else "Federal Agency",
                    "responseDeadLine": deadline,
                    "uiLink": f"https://sam.gov/opp/{r.get('_id')}/view" if r.get("_id") else "https://sam.gov",
                    "description": str(desc)[:600]
                })
    except Exception as e:
        print(f"Fetch error for {query_text}: {e}")

    return bids

def format_clean_digest(bids):
    output = []
    for b in bids:
        output.append(
            f"- **Project & Agency**: {b.get('title')} | {b.get('department')}\n"
            f"- **Deadline**: {b.get('responseDeadLine')} | **Sol #**: {b.get('solicitationNumber')}\n"
            f"- **Scope**: {b.get('description')}\n"
            f"- **Link**: {b.get('uiLink')}\n"
        )
    return "\n".join(output)

def create_gmail_draft(user, password, recipient_list, subject, body):
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = ", ".join(recipient_list)
    msg["Subject"] = subject
    msg.set_content(body)

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(user, password)
    mail.append('"[Gmail]/Drafts"', "\\Draft", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
    mail.logout()

def main():
    gmail_user = os.environ.get("SENDER_EMAIL")
    gmail_pass = os.environ.get("APP_PASSWORD")

    if not all([gmail_user, gmail_pass]):
        print("Missing Gmail credentials. Exiting.")
        return

    already_sent = load_sent_ids()
    new_ids_to_commit = []

    for category, config in TRADE_CONFIG.items():
        print(f"Scanning SAM.gov for trade: {category}...")
        raw_bids = fetch_trade_opportunities(config["search_query"])
        
        matched_bids = []
        for opp in raw_bids:
            nid = opp.get("noticeId")
            if not nid or nid in already_sent:
                continue

            searchable = f"{opp.get('title', '')} {opp.get('description', '')}".lower()
            if any(k in searchable for k in config["keywords"]):
                matched_bids.append(opp)

        if not matched_bids:
            print(f"[{category}] No fresh bids found right now.")
            continue

        print(f"[{category}] Matched {len(matched_bids)} bids. Creating draft...")
        brief = format_clean_digest(matched_bids[:3])  # Top 3 most relevant per email
        full_body = config["intro"] + brief + PITCH_SIGNATURE
        subject = f"Federal Commercial {category} Opportunities - {datetime.now().strftime('%b %d')}"

        create_gmail_draft(gmail_user, gmail_pass, config["recipients"], subject, full_body)
        print(f"[{category}] Draft created successfully.")

        for b in matched_bids:
            new_ids_to_commit.append(b["noticeId"])
            already_sent.add(b["noticeId"])
            
        time.sleep(1)

    if new_ids_to_commit:
        save_sent_ids(new_ids_to_commit)
        print(f"Committed {len(new_ids_to_commit)} total IDs.")

if __name__ == "__main__":
    main()
