from datetime import datetime, timezone
from time import monotonic
import json

from util import get_settings, get_db


SETTINGS = get_settings()
db = get_db()
USER_ID = SETTINGS["USER_ID"]
with open("index.html") as f:
    index_page = f.read()
with open("overlay.html") as f:
    overlay_page = f.read()


def get_time_passed(seconds):
    times = (
        ("second", 60),
        ("minute", 60),
        ("hour", 24),
        ("day", 365/12),
        ("month", 12),
        ("year", 9999)
    )
    
    value = seconds
    text = f"{value} second" + "s" if value != 1 else ""
    for i in range(len(times)):
        label, divisor = times[i]
        value, bounded_value = divmod(value, divisor)
        if value == 0:
            break
        next_label = times[i+1][0] + ("s" if value != 1 else "")
        text = f"{round(value)} {next_label} {round(bounded_value)} {label + ('s' if bounded_value != 1 else '')}"
        
    return text


def get_score_html(score):
    time_passed = get_time_passed(round((datetime.now(tz=timezone.utc) - datetime.fromisoformat(score[6])).total_seconds()))
    html = (
        '<div class="score">\n'
        '   <div class="score-section grow">\n'
        f'      <p class="big">{score[3]} - {score[4]} [{score[5]}]</p>\n'
        '       <p class="small">%dx / %dx { %d / %d / %d / %d } %s ago</p>\n'
        '   </div>\n'
        '   <div class="score-section">\n'
        f'      <p class="ultra">{score[14]}</p>\n'
        '   </div>\n'
        '   <div class="score-section" style="width: 60px;">\n'
        f'      <p class="ultra" style="color: #ffc34b;">%.2f%%</p>\n'
        '   </div>\n'
        '   <div class="score-section" style="width: 50px;">\n'
        f'      <p class="ultra" style="color: #ff66ab;">{round(score[1])}pp</p>\n'
        '   </div>\n'
        '</div>\n' % (score[8], score[9], score[10], score[11], score[12], score[13], time_passed, round(score[7]*100, 2))
    )
    if score[15] != 0:
        html = f'<a href="https://osu.ppy.sh/scores/osu/{score[0]}" target="_blank">' + html[:-1] + '</a>\n'
    else:
        html = f'<a>' + html[:-1] + '</a>\n'
    return html


def score_container(scores):
    return '<div class="score-container">\n' + "\n".join(map(get_score_html, scores)) + '</div>'


def rank_header(rank, total_pp):
    return f"<h1>Rank #{rank} ({round(total_pp, 2)}pp)</h1>\n"


def graph_container():
    return (
        '<div id="graph-container">\n'
        '   <div id="graph-marker" class="hidden"></div>\n'
        '   <div id="graph-label" class="prevent-select hidden">\n'
        '       <p id="rank-label"></p>\n'
        '       <p id="time-label"></p>\n'
        '   </div>\n'
        '   <svg width="500" height="100"><path/></svg>\n'
        '</div>\n'
    )


def page_content(rank, total_pp, scores):
    return rank_header(rank, total_pp) + graph_container() + score_container(scores)


async def get_page():
    cursor = db.cursor()
    cursor.execute("SELECT *, MAX(pp) AS topplay FROM scores GROUP BY beatmap_id ORDER BY topplay DESC LIMIT 100")
    scores = cursor.fetchall()
    cursor.execute(f"SELECT total_pp, rank, pp_history, rank_history FROM stats WHERE user_id = {USER_ID}")
    total_pp, rank, pp_history, rank_history = cursor.fetchone()
    content = page_content(rank, total_pp, scores)
    pp_history, rank_history = json.loads(pp_history), json.loads(rank_history)
    return index_page.replace("{% content %}", content).replace("{% pp_history %}", json.dumps(pp_history[-90:])).replace("{% rank_history %}", json.dumps(rank_history[-90:]))


async def get_overlay():
    return overlay_page


data_cache = None
last_cache = monotonic()-5


async def get_data():
    global data_cache
    global last_cache

    if monotonic()-last_cache >= 1 or data_cache is None:
        cursor = db.cursor()
        cursor.execute(f"SELECT total_pp, rank, pp_history, rank_history FROM stats WHERE user_id = {USER_ID}")
        total_pp, rank, pp_history, rank_history = cursor.fetchone()
        data_cache = json.dumps({
            "totalPp": total_pp,
            "rank": rank,
            "ppHistory": pp_history,
            "rankHistory": rank_history
        }).encode("ascii")
    return data_cache


async def app(scope, receive, send):
    pathing = {
        "": get_page,
        "/overlay": get_overlay,
        "/data": get_data
    }
    memtypes = {
        "/data": "application/json"
    }
    assert scope["type"] == "http"

    path = scope["path"].strip().lower()
    if path.endswith("/"):
        path = path[:-1]
    if path not in pathing:
        await send({
            "type": "http.response.start",
            "status": 404
        })
        return await send({
            "type": "http.response.body",
            "body": b""
        })
    
    mt = memtypes.get(path, "text/html")
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            [b"content-type", mt.encode("ascii")],
            [b"encoding", "utf-8"]
        ]
    })
    body = await pathing[path]()
    if mt == "text/html":
        body = body.encode("utf-8")
    await send({
        "type": "http.response.body",
        "body": body
    })
    
