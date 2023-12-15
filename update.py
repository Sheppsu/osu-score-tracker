from osu import Client, SoloScore, RankStatus
from time import sleep
from datetime import datetime, timezone
from osu_diff_calc import OsuPerformanceCalculator, OsuDifficultyAttributes, OsuScoreAttributes
import json
import requests
import math

from util import get_settings, get_db


SETTINGS = get_settings()
db = get_db()
client = Client.from_client_credentials(int(SETTINGS["CLIENT_ID"]), SETTINGS["CLIENT_SECRET"], None, request_wait_time=0)
USER_ID = SETTINGS["USER_ID"]
last_viewed_score = None


def sqlstr(s):
    return "'"+s.replace("'", "''")+"'"


def get_rank(total_pp):
    if round(total_pp) == 0:
        return 0
    try:
        resp = requests.get(f"https://osudaily.net/data/getPPRank.php?t=pp&v={round(total_pp)}&m=0")
        return int(resp.text)
    except:
        print("uh, failed to get rank")


def calculate_total_pp(scores):
    total_pp = 0
    for i, score in enumerate(scores):
        total_pp += score[1] * math.pow(0.95, i)
    bonus_pp = 416.6667 * (1 - math.pow(0.9994, len(scores)))
    return total_pp + bonus_pp


def update_new_day(cursor):
    cursor.execute(f"SELECT pp_history, rank_history, start_date FROM stats WHERE user_id = {USER_ID}")
    pp_history, rank_history, start_date = cursor.fetchone()
    pp_history, rank_history = json.loads(pp_history), json.loads(rank_history)
    days = (datetime.now(tz=timezone.utc) - datetime.fromisoformat(start_date)).days
    increased = False
    new_rank = None
    while days >= len(pp_history):
        if new_rank is None:
            new_rank = get_rank(pp_history[-1])
            if new_rank is None:
                return False, pp_history, rank_history
        increased = True
        pp_history.append(pp_history[-1])
        rank_history.append(new_rank)
    return increased, pp_history, rank_history


def update_stats(cursor):
    _, pp_history, rank_history = update_new_day(cursor)

    cursor.execute("SELECT *, MAX(pp) AS topplay FROM scores GROUP BY beatmap_id ORDER BY topplay DESC")
    scores = cursor.fetchall()
    total_pp = calculate_total_pp(scores)
    rank = get_rank(total_pp)
    if rank is None:
        return

    pp_history[-1] = total_pp
    rank_history[-1] = rank
    
    cursor.execute(f"UPDATE stats SET total_pp = {total_pp}, rank = {rank}, pp_history = '{json.dumps(pp_history)}', rank_history = '{json.dumps(rank_history)}' WHERE user_id = {USER_ID}")
    db.commit()


def calculate_pp(score: SoloScore, beatmap):
    tries = 0
    while True:
        try:
            tries += 1
            beatmap_attributes = client.get_beatmap_attributes(
                score.beatmap_id,
                mods=list(map(lambda m: m.mod.value, score.mods)),
                ruleset_id=score.ruleset_id
            )
            break
        except:
            if tries == 5:
                print("Unable to get difficulty attributes for beatmap")
                return
            sleep(1)

    return OsuPerformanceCalculator(
        score.ruleset_id,
        OsuDifficultyAttributes.from_attributes({
            'aim_difficulty': beatmap_attributes.mode_attributes.aim_difficulty,
            'speed_difficulty': beatmap_attributes.mode_attributes.speed_difficulty,
            'flashlight_difficulty': beatmap_attributes.mode_attributes.flashlight_difficulty,
            'slider_factor': beatmap_attributes.mode_attributes.slider_factor,
            'speed_note_count': beatmap_attributes.mode_attributes.speed_note_count,
            'approach_rate': beatmap_attributes.mode_attributes.approach_rate,
            'overall_difficulty': beatmap_attributes.mode_attributes.overall_difficulty,
            'max_combo': beatmap_attributes.max_combo,
            'drain_rate': beatmap.drain,
            'hit_circle_count': beatmap.count_circles,
            'slider_count': beatmap.count_sliders,
            'spinner_count': beatmap.count_spinners,
        }),
        OsuScoreAttributes.from_osupy_score(score)
    ).calculate()


def add_scores():
    global last_viewed_score

    cursor = db.cursor()
    increased, pp_history, rank_history = update_new_day(cursor)
    if increased:
        cursor.execute(f"UPDATE stats SET pp_history = '{json.dumps(pp_history)}', rank_history = '{json.dumps(rank_history)}', rank = {rank_history[-1]} WHERE user_id = {USER_ID}")
        db.commit()

    for score in client.get_user_scores(USER_ID, "recent", mode="osu", limit=1):
        if last_viewed_score == score.id:
            return
        last_viewed_score = score.id

        beatmap = client.get_beatmap(score.beatmap_id)
        if beatmap.status != RankStatus.RANKED and beatmap.status != RankStatus.APPROVED:
            return
        if score.pp is None:
            score.pp = calculate_pp(score, beatmap)
            if score.pp is None:
                return
        hits = score.statistics
        mods = "".join(map(lambda m: m.mod.value, score.mods)) if score.mods else ""
        cursor.execute(f"INSERT OR IGNORE INTO scores (id, pp, beatmap_id, artist, title, difficulty, timestamp, accuracy, combo, max_combo, hit300, hit100, hit50, hit0, mods, valid_id) VALUES ({score.best_id or score.id}, {score.pp}, {score.beatmap_id}, {sqlstr(beatmap.beatmapset.artist)}, {sqlstr(beatmap.beatmapset.title)}, {sqlstr(beatmap.version)}, {sqlstr(score.ended_at.isoformat())}, {score.accuracy}, {score.max_combo}, {beatmap.max_combo}, {hits.great or 0}, {hits.ok or 0}, {hits.meh or 0}, {hits.miss or 0}, {sqlstr(mods)}, {0 if score.best_id is None else 1})")
        db.commit()

        update_stats(cursor)


def run():
    while True:
        add_scores()
        sleep(5)


if __name__ == "__main__":
    run()
