import os, re, json, time, hashlib, requests
from bs4 import BeautifulSoup

# 검사할 페이지(서울 계약마당 공고 목록)
BASE_URL = "https://contract.seoul.go.kr/new1/views/pubBidInfo.do"

# 🔧 여기 키워드를 원하는 걸로 바꿔서 쓰면 돼!
KEYWORDS = ["유튜브", "영상", "브랜딩", "인플루언서", "라이브커머스", "디자인"]

# 슬랙 웹훅은 GitHub에 비밀로 넣어둘 거라 환경변수에서 읽어옴
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK")

# 중복 알림 방지용(이미 본 공고를 기록)
STATE_FILE = "seen.json"

def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()

def load_state():
    if os.path.exists(STATE_FILE):
        return set(json.load(open(STATE_FILE, "r", encoding="utf-8")))
    return set()

def save_state(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)

def sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def fetch_list():
    # 페이지의 표를 읽어서 각 행마다 제목/링크를 뽑아낸다
    r = requests.get(BASE_URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    items = []
    if not table:
        return items
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        title = norm(tds[1].get_text(" "))
        org = norm(tds[0].get_text(" "))
        dates = " | ".join(norm(td.get_text(" ")) for td in tds[2:])
        a = tr.find("a")
        href = a.get("href") if a else None
        link = requests.compat.urljoin(BASE_URL, href) if href else BASE_URL
        if title:
            items.append({"title": title, "org": org, "dates": dates, "link": link})
    return items

def hit(title):
    t = norm(title)
    return any(k.lower() in t for k in KEYWORDS)

def post_to_slack(item):
    text = f"*{item['title']}*\n기관/유형: {item['org']}\n일정: {item['dates']}\n링크: {item['link']}"
    r = requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    r.raise_for_status()

def main():
    if not SLACK_WEBHOOK:
        raise SystemExit("SLACK_WEBHOOK 미설정 (GitHub Secrets에 추가해야 해요)")
    seen = load_state()
    new_hits = []
    for it in fetch_list():
        uid = sha(it["title"] + it["link"])
        if uid in seen:
            continue
        if hit(it["title"]):
            new_hits.append(it)
        seen.add(uid)  # 본 건은 기록(중복방지)
    # 오래된 것부터 보내기
    for it in reversed(new_hits):
        post_to_slack(it)
        time.sleep(0.3)
    save_state(seen)

if __name__ == "__main__":
    main()
