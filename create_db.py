from datetime import datetime, timezone
import sqlite3 as sql
import os

from util import get_settings


SETTINGS = get_settings()


def create_db():
    if os.path.isfile("data.db"):
        print("data.db already exists. Delete it or rename it if you want a fresh db.")
        quit()

    db = sql.connect("data.db")
    cursor = db.cursor()
    cursor.execute('CREATE TABLE "scores" (\
        "id" INTEGER NOT NULL UNIQUE,\
        "pp" REAL NOT NULL,\
        "beatmap_id" INTEGER NOT NULL,\
        "artist" TEXT,\
        "title"	TEXT,\
        "difficulty" TEXT,\
        "timestamp" TEXT,\
        "accuracy" REAL,\
        "combo"	INTEGER,\
        "max_combo"	INTEGER,\
        "hit300" INTEGER,\
        "hit100" INTEGER,\
        "hit50"	INTEGER,\
        "hit0" INTEGER,\
        "mods" TEXT,\
        "valid_id"	INTEGER,\
        PRIMARY KEY("id")\
    )')
    db.commit()
    cursor.execute('CREATE TABLE "stats" (\
        "user_id" INTEGER NOT NULL UNIQUE,\
        "total_pp" REAL NOT NULL,\
        "rank" INTEGER NOT NULL,\
        "pp_history" TEXT NOT NULL,\
        "rank_history" TEXT NOT NULL,\
        "start_date" TEXT NOT NULL,\
        PRIMARY KEY("user_id")\
    )')
    db.commit()
    now = datetime.now(tz=timezone.utc).isoformat()
    cursor.execute("INSERT INTO stats (user_id, total_pp, rank, pp_history, rank_history, start_date) "
                   f"VALUES ({SETTINGS['USER_ID']}, 0, 0, '[0]', '[0]', '{now}')")
    db.commit()


if __name__ == "__main__":
    create_db()
