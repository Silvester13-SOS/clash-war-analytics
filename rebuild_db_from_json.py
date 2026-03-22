"""
Rebuild war_data.db from exported JSON files in docs/data/.
Use this to recover data if the database was lost.
Run BEFORE war_collector.py to establish a base, then the collector will add new data.
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "war_data.db")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data")


def init_db(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS wars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        war_end_time TEXT UNIQUE,
        clan_tag TEXT,
        clan_name TEXT,
        clan_stars INTEGER,
        clan_destruction REAL,
        opponent_tag TEXT,
        opponent_name TEXT,
        opponent_stars INTEGER,
        opponent_destruction REAL,
        team_size INTEGER,
        attacks_per_member INTEGER DEFAULT 2,
        result TEXT,
        war_type TEXT DEFAULT 'regular',
        collected_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS attacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        war_id INTEGER,
        attacker_tag TEXT,
        attacker_name TEXT,
        attacker_th_level INTEGER,
        attacker_map_position INTEGER,
        defender_tag TEXT,
        defender_name TEXT,
        defender_th_level INTEGER,
        defender_map_position INTEGER,
        stars INTEGER,
        destruction_percentage REAL,
        attack_order INTEGER,
        duration INTEGER,
        FOREIGN KEY (war_id) REFERENCES wars(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS clan_meta (
        clan_tag TEXT PRIMARY KEY,
        clan_name TEXT,
        badge_url TEXT,
        clan_level INTEGER,
        war_wins INTEGER,
        win_streak INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS defenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        war_id INTEGER,
        defender_tag TEXT,
        defender_name TEXT,
        defender_th_level INTEGER,
        defender_map_position INTEGER,
        attacker_tag TEXT,
        attacker_name TEXT,
        attacker_th_level INTEGER,
        stars_received INTEGER,
        destruction_received REAL,
        attack_order INTEGER,
        FOREIGN KEY (war_id) REFERENCES wars(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS player_heroes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_tag TEXT,
        hero_name TEXT,
        hero_level INTEGER,
        max_level INTEGER,
        UNIQUE(player_tag, hero_name)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS player_equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_tag TEXT,
        equipment_name TEXT,
        equipment_level INTEGER,
        max_level INTEGER,
        hero_name TEXT,
        UNIQUE(player_tag, equipment_name)
    )""")
    conn.commit()


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def rebuild():
    if os.path.exists(DB_PATH):
        print(f"Database already exists at {DB_PATH}")
        print("Delete it first if you want a full rebuild.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    c = conn.cursor()

    # Load war history (contains all wars)
    wars_data = load_json(os.path.join(DATA_DIR, "war-history.json"))
    if not wars_data:
        print("No war-history.json found. Nothing to recover.")
        conn.close()
        return

    print(f"Found {len(wars_data)} wars in war-history.json")

    old_to_new_id = {}

    for war in wars_data:
        attacks_per_member = 1 if war["war_type"] == "cwl" else 2
        try:
            c.execute("""INSERT INTO wars (war_end_time, clan_tag, clan_name, clan_stars,
                        clan_destruction, opponent_tag, opponent_name, opponent_stars,
                        opponent_destruction, team_size, attacks_per_member, result, war_type,
                        collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (war["end_time"], "", war["clan_name"], war["clan_stars"],
                       war["clan_destruction"], "", war["opponent_name"],
                       war["opponent_stars"], war["opponent_destruction"],
                       war["team_size"], attacks_per_member, war["result"],
                       war["war_type"], "recovered-from-json"))
            new_id = c.lastrowid
            old_to_new_id[war["id"]] = new_id
            print(f"  Recovered war: vs {war['opponent_name']} ({war['result']}) -> id {new_id}")
        except sqlite3.IntegrityError:
            print(f"  War vs {war['opponent_name']} already exists, skipping")

    # Load per-war attack details
    war_dir = os.path.join(DATA_DIR, "war")
    if os.path.isdir(war_dir):
        for old_id, new_id in old_to_new_id.items():
            attacks = load_json(os.path.join(war_dir, f"{old_id}.json"))
            if attacks:
                for atk in attacks:
                    c.execute("""INSERT INTO attacks (war_id, attacker_tag, attacker_name,
                                attacker_th_level, attacker_map_position, defender_tag,
                                defender_name, defender_th_level, defender_map_position,
                                stars, destruction_percentage, attack_order, duration)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                              (new_id, "", atk["attacker_name"],
                               atk.get("attacker_th", 0), atk.get("attacker_position", 0),
                               "", atk["defender_name"],
                               atk.get("defender_th", 0), atk.get("defender_position", 0),
                               atk["stars"], atk["destruction"],
                               atk.get("order", 0), atk.get("duration", 0)))
                print(f"  Recovered {len(attacks)} attacks for war id {new_id}")

    # Load clan summary for metadata
    summary = load_json(os.path.join(DATA_DIR, "clan-summary.json"))
    if summary and summary.get("badge_url"):
        c.execute("""INSERT OR REPLACE INTO clan_meta (clan_tag, clan_name, badge_url, clan_level, war_wins, win_streak)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                  ("", summary.get("clan_name", ""),
                   summary.get("badge_url", ""), summary.get("clan_level", 0),
                   summary.get("war_wins", 0), summary.get("win_streak", 0)))

    conn.commit()
    conn.close()
    print(f"\nDatabase rebuilt at {DB_PATH}")
    print("Run war_collector.py next to fill in missing tags and collect new data.")


if __name__ == "__main__":
    rebuild()
