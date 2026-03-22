"""
Export war_data.db to static JSON files for GitHub Pages.
Mirrors all Flask API endpoints so the static dashboard works identically.
"""
import sqlite3
import json
import csv
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "war_data.db")
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
DATA_DIR = os.path.join(DOCS_DIR, "data")


def _fix_stars(stars, destruction):
    """Enforce Clash of Clans star rules: 100% = 3 stars, >=50% = at least 1 star."""
    if destruction >= 100:
        return 3
    if destruction >= 50 and stars < 1:
        return 1
    return stars


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "war"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "player"), exist_ok=True)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def export_player_stats(conn, war_type="all"):
    c = conn.cursor()
    where, params = "", ()
    if war_type in ("regular", "cwl"):
        where = "WHERE w.war_type = ?"
        params = (war_type,)

    c.execute(f"""
        SELECT
            a.attacker_name, a.attacker_tag,
            COUNT(*) as total_attacks,
            SUM(CASE WHEN a.stars = 3 THEN 1 ELSE 0 END) as three_stars,
            SUM(CASE WHEN a.stars = 2 THEN 1 ELSE 0 END) as two_stars,
            SUM(CASE WHEN a.stars = 1 THEN 1 ELSE 0 END) as one_stars,
            SUM(CASE WHEN a.stars = 0 THEN 1 ELSE 0 END) as zero_stars,
            ROUND(AVG(a.destruction_percentage), 1) as avg_destruction,
            ROUND(AVG(a.stars), 2) as avg_stars,
            MAX(a.attacker_th_level) as th_level,
            COUNT(DISTINCT a.war_id) as wars_participated
        FROM attacks a
        JOIN wars w ON a.war_id = w.id
        {where}
        GROUP BY a.attacker_tag
        ORDER BY avg_stars DESC, avg_destruction DESC
    """, params)

    players = []
    for row in c.fetchall():
        total = row["total_attacks"]
        players.append({
            "name": row["attacker_name"],
            "tag": row["attacker_tag"],
            "th_level": row["th_level"],
            "total_attacks": total,
            "wars_participated": row["wars_participated"],
            "three_star_pct": round(row["three_stars"] / total * 100, 1),
            "two_star_pct": round(row["two_stars"] / total * 100, 1),
            "one_star_pct": round(row["one_stars"] / total * 100, 1),
            "zero_star_pct": round(row["zero_stars"] / total * 100, 1),
            "three_stars": row["three_stars"],
            "two_stars": row["two_stars"],
            "one_stars": row["one_stars"],
            "zero_stars": row["zero_stars"],
            "avg_destruction": row["avg_destruction"],
            "avg_stars": row["avg_stars"],
        })
    return players


def export_war_history(conn, war_type="all"):
    c = conn.cursor()
    where, params = "", ()
    if war_type in ("regular", "cwl"):
        where = "WHERE w.war_type = ?"
        params = (war_type,)

    c.execute(f"""
        SELECT w.*,
            (SELECT COUNT(*) FROM attacks a WHERE a.war_id = w.id) as attack_count
        FROM wars w
        {where}
        ORDER BY w.war_end_time DESC
    """, params)

    wars = []
    for row in c.fetchall():
        wars.append({
            "id": row["id"],
            "end_time": row["war_end_time"],
            "clan_name": row["clan_name"],
            "clan_stars": row["clan_stars"],
            "clan_destruction": round(row["clan_destruction"], 1),
            "opponent_name": row["opponent_name"],
            "opponent_stars": row["opponent_stars"],
            "opponent_destruction": round(row["opponent_destruction"], 1),
            "team_size": row["team_size"],
            "result": row["result"],
            "war_type": row["war_type"],
            "attack_count": row["attack_count"],
        })
    return wars


def export_clan_summary(conn, war_type="all"):
    c = conn.cursor()
    war_where, atk_join, params = "", "", ()
    if war_type in ("regular", "cwl"):
        war_where = "WHERE war_type = ?"
        atk_join = "JOIN wars w ON a.war_id = w.id WHERE w.war_type = ?"
        params = (war_type,)

    c.execute(f"SELECT COUNT(*) FROM wars {war_where}", params)
    total_wars = c.fetchone()[0]

    c.execute(f"SELECT COUNT(*) FROM wars {war_where and war_where + ' AND result = ?' or 'WHERE result = ?'}", (*params, "win"))
    wins = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM wars {war_where and war_where + ' AND result = ?' or 'WHERE result = ?'}", (*params, "loss"))
    losses = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM wars {war_where and war_where + ' AND result = ?' or 'WHERE result = ?'}", (*params, "tie"))
    ties = c.fetchone()[0]

    if atk_join:
        c.execute(f"SELECT COUNT(*) FROM attacks a {atk_join}", params)
    else:
        c.execute("SELECT COUNT(*) FROM attacks")
    total_attacks = c.fetchone()[0]

    if atk_join:
        c.execute(f"SELECT ROUND(AVG(a.stars), 2) FROM attacks a {atk_join}", params)
    else:
        c.execute("SELECT ROUND(AVG(stars), 2) FROM attacks")
    avg_stars = c.fetchone()[0] or 0

    if atk_join:
        c.execute(f"SELECT ROUND(AVG(a.destruction_percentage), 1) FROM attacks a {atk_join}", params)
    else:
        c.execute("SELECT ROUND(AVG(destruction_percentage), 1) FROM attacks")
    avg_destruction = c.fetchone()[0] or 0

    c.execute("SELECT clan_name, clan_tag FROM wars ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    clan_name = row[0] if row else "Unknown"
    clan_tag = row[1] if row else ""

    clan_meta = {}
    try:
        c.execute("SELECT badge_url, clan_level, war_wins, win_streak FROM clan_meta WHERE clan_tag = ?", (clan_tag,))
        mrow = c.fetchone()
        if mrow:
            clan_meta = {"badge_url": mrow[0], "clan_level": mrow[1], "war_wins": mrow[2], "win_streak": mrow[3]}
    except Exception:
        pass

    return {
        "clan_name": clan_name,
        "total_wars": total_wars,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "total_attacks": total_attacks,
        "avg_stars": avg_stars,
        "avg_destruction": avg_destruction,
        **clan_meta,
    }


def export_defense_stats(conn, war_type="all"):
    c = conn.cursor()
    where, params = "", ()
    if war_type in ("regular", "cwl"):
        where = "AND w.war_type = ?"
        params = (war_type,)

    c.execute(f"""
        SELECT
            d.defender_name, d.defender_tag,
            MAX(d.defender_th_level) as th_level,
            COUNT(*) as times_attacked,
            ROUND(AVG(d.stars_received), 2) as avg_stars_given,
            ROUND(AVG(d.destruction_received), 1) as avg_dest_given,
            SUM(CASE WHEN d.stars_received = 3 THEN 1 ELSE 0 END) as gave_3,
            SUM(CASE WHEN d.stars_received = 2 THEN 1 ELSE 0 END) as gave_2,
            SUM(CASE WHEN d.stars_received = 1 THEN 1 ELSE 0 END) as gave_1,
            SUM(CASE WHEN d.stars_received = 0 THEN 1 ELSE 0 END) as gave_0,
            COUNT(DISTINCT d.war_id) as wars_defended
        FROM defenses d
        JOIN wars w ON d.war_id = w.id
        WHERE 1=1 {where}
        GROUP BY d.defender_tag
        ORDER BY avg_stars_given ASC
    """, params)

    players = []
    for row in c.fetchall():
        t = row["times_attacked"]
        players.append({
            "name": row["defender_name"],
            "tag": row["defender_tag"],
            "th_level": row["th_level"],
            "times_attacked": t,
            "wars_defended": row["wars_defended"],
            "avg_stars_given": row["avg_stars_given"],
            "avg_dest_given": row["avg_dest_given"],
            "three_starred_pct": round(row["gave_3"] / t * 100, 1),
            "two_starred_pct": round(row["gave_2"] / t * 100, 1),
            "one_starred_pct": round(row["gave_1"] / t * 100, 1),
            "zero_starred_pct": round(row["gave_0"] / t * 100, 1),
            "defense_rating": round(3.0 - (row["avg_stars_given"] or 0), 2),
        })
    return players


def export_war_attacks(conn, war_id):
    c = conn.cursor()
    c.execute("SELECT * FROM attacks WHERE war_id = ? ORDER BY attack_order", (war_id,))
    attacks = []
    for row in c.fetchall():
        attacks.append({
            "attacker_name": row["attacker_name"],
            "attacker_th": row["attacker_th_level"],
            "attacker_position": row["attacker_map_position"],
            "defender_name": row["defender_name"],
            "defender_th": row["defender_th_level"],
            "defender_position": row["defender_map_position"],
            "stars": _fix_stars(row["stars"], row["destruction_percentage"]),
            "destruction": row["destruction_percentage"],
            "order": row["attack_order"],
            "duration": row["duration"],
        })
    return attacks


def export_player_detail(conn, player_tag):
    c = conn.cursor()

    c.execute("SELECT hero_name, hero_level, max_level FROM player_heroes WHERE player_tag = ? ORDER BY hero_name",
              (player_tag,))
    heroes = [{"name": r["hero_name"], "level": r["hero_level"], "max_level": r["max_level"]} for r in c.fetchall()]

    c.execute("SELECT equipment_name, equipment_level, max_level, hero_name FROM player_equipment WHERE player_tag = ? ORDER BY hero_name, equipment_name",
              (player_tag,))
    equipment = [{"name": r["equipment_name"], "level": r["equipment_level"], "max_level": r["max_level"], "hero": r["hero_name"]} for r in c.fetchall()]

    c.execute("""
        SELECT a.*, w.opponent_name, w.war_end_time, w.war_type, w.result
        FROM attacks a JOIN wars w ON a.war_id = w.id
        WHERE a.attacker_tag = ?
        ORDER BY w.war_end_time DESC, a.attack_order
    """, (player_tag,))
    attacks = []
    for r in c.fetchall():
        attacks.append({
            "opponent": r["opponent_name"],
            "war_date": r["war_end_time"],
            "war_type": r["war_type"],
            "war_result": r["result"],
            "defender_name": r["defender_name"],
            "defender_th": r["defender_th_level"],
            "defender_position": r["defender_map_position"],
            "stars": _fix_stars(r["stars"], r["destruction_percentage"]),
            "destruction": r["destruction_percentage"],
            "order": r["attack_order"],
            "duration": r["duration"],
        })

    stats = {}
    for wt in ("regular", "cwl"):
        c.execute("""
            SELECT COUNT(*) as total,
                SUM(CASE WHEN a.stars = 3 THEN 1 ELSE 0 END) as s3,
                SUM(CASE WHEN a.stars = 2 THEN 1 ELSE 0 END) as s2,
                SUM(CASE WHEN a.stars = 1 THEN 1 ELSE 0 END) as s1,
                SUM(CASE WHEN a.stars = 0 THEN 1 ELSE 0 END) as s0,
                ROUND(AVG(a.stars), 2) as avg_stars,
                ROUND(AVG(a.destruction_percentage), 1) as avg_dest
            FROM attacks a JOIN wars w ON a.war_id = w.id
            WHERE a.attacker_tag = ? AND w.war_type = ?
        """, (player_tag, wt))
        row = c.fetchone()
        if row and row["total"] > 0:
            t = row["total"]
            stats[wt] = {
                "total": t,
                "three_star_pct": round(row["s3"] / t * 100, 1),
                "two_star_pct": round(row["s2"] / t * 100, 1),
                "one_star_pct": round(row["s1"] / t * 100, 1),
                "zero_star_pct": round(row["s0"] / t * 100, 1),
                "avg_stars": row["avg_stars"],
                "avg_dest": row["avg_dest"],
            }

    c.execute("""
        SELECT COUNT(*) as times_attacked,
            ROUND(AVG(d.stars_received), 2) as avg_stars_given,
            ROUND(AVG(d.destruction_received), 1) as avg_dest_given,
            SUM(CASE WHEN d.stars_received = 3 THEN 1 ELSE 0 END) as gave_3,
            SUM(CASE WHEN d.stars_received <= 1 THEN 1 ELSE 0 END) as held_to_1_or_less
        FROM defenses d WHERE d.defender_tag = ?
    """, (player_tag,))
    drow = c.fetchone()
    defense = None
    if drow and drow["times_attacked"] > 0:
        t = drow["times_attacked"]
        defense = {
            "times_attacked": t,
            "avg_stars_given": drow["avg_stars_given"],
            "avg_dest_given": drow["avg_dest_given"],
            "three_starred_pct": round(drow["gave_3"] / t * 100, 1),
            "held_pct": round(drow["held_to_1_or_less"] / t * 100, 1),
            "defense_rating": round(3.0 - (drow["avg_stars_given"] or 0), 2),
        }

    c.execute("""
        SELECT d.*, w.opponent_name, w.war_end_time, w.war_type
        FROM defenses d JOIN wars w ON d.war_id = w.id
        WHERE d.defender_tag = ?
        ORDER BY w.war_end_time DESC, d.attack_order
    """, (player_tag,))
    defense_log = []
    for r in c.fetchall():
        defense_log.append({
            "opponent": r["opponent_name"],
            "war_date": r["war_end_time"],
            "war_type": r["war_type"],
            "attacker_name": r["attacker_name"],
            "attacker_th": r["attacker_th_level"],
            "stars_received": r["stars_received"],
            "destruction_received": r["destruction_received"],
        })

    return {
        "heroes": heroes,
        "equipment": equipment,
        "attacks": attacks,
        "stats_by_type": stats,
        "defense": defense,
        "defense_log": defense_log,
    }


MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def export_cwl_seasons(conn):
    """Return list of CWL seasons derived from war dates."""
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT SUBSTR(war_end_time, 1, 4) as year, SUBSTR(war_end_time, 5, 2) as month
        FROM wars WHERE war_type = 'cwl' ORDER BY year DESC, month DESC
    """)
    seasons = []
    for row in c.fetchall():
        y, m = int(row["year"]), int(row["month"])
        c2 = conn.cursor()
        c2.execute("""
            SELECT COUNT(*) as war_count,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'tie' THEN 1 ELSE 0 END) as ties
            FROM wars WHERE war_type = 'cwl' AND war_end_time LIKE ?
        """, (f"{y}{str(m).zfill(2)}%",))
        s = c2.fetchone()
        seasons.append({
            "year": y, "month": m, "label": f"{MONTH_NAMES[m]} {y}",
            "war_count": s["war_count"], "wins": s["wins"],
            "losses": s["losses"], "ties": s["ties"],
        })
    return seasons


def export_cwl_season_detail(conn, year, month):
    """Return full season detail for a specific CWL month."""
    prefix = f"{year}{str(month).zfill(2)}%"
    where = "WHERE w.war_type = 'cwl' AND w.war_end_time LIKE ?"
    params = (prefix,)
    c = conn.cursor()

    # Player stats
    c.execute(f"""
        SELECT a.attacker_name, a.attacker_tag, COUNT(*) as total_attacks,
            SUM(CASE WHEN a.stars = 3 THEN 1 ELSE 0 END) as three_stars,
            SUM(CASE WHEN a.stars = 2 THEN 1 ELSE 0 END) as two_stars,
            SUM(CASE WHEN a.stars = 1 THEN 1 ELSE 0 END) as one_stars,
            SUM(CASE WHEN a.stars = 0 THEN 1 ELSE 0 END) as zero_stars,
            ROUND(AVG(a.destruction_percentage), 1) as avg_destruction,
            ROUND(AVG(a.stars), 2) as avg_stars,
            MAX(a.attacker_th_level) as th_level,
            COUNT(DISTINCT a.war_id) as wars_participated
        FROM attacks a JOIN wars w ON a.war_id = w.id {where}
        GROUP BY a.attacker_tag ORDER BY avg_stars DESC, avg_destruction DESC
    """, params)
    players = []
    for row in c.fetchall():
        t = row["total_attacks"]
        players.append({
            "name": row["attacker_name"], "tag": row["attacker_tag"],
            "th_level": row["th_level"], "total_attacks": t,
            "wars_participated": row["wars_participated"],
            "three_star_pct": round(row["three_stars"] / t * 100, 1),
            "two_star_pct": round(row["two_stars"] / t * 100, 1),
            "one_star_pct": round(row["one_stars"] / t * 100, 1),
            "zero_star_pct": round(row["zero_stars"] / t * 100, 1),
            "three_stars": row["three_stars"], "two_stars": row["two_stars"],
            "one_stars": row["one_stars"], "zero_stars": row["zero_stars"],
            "avg_destruction": row["avg_destruction"], "avg_stars": row["avg_stars"],
        })

    # Wars
    c.execute(f"""
        SELECT w.*, (SELECT COUNT(*) FROM attacks a WHERE a.war_id = w.id) as attack_count
        FROM wars w {where} ORDER BY w.war_end_time ASC
    """, params)
    wars = []
    for row in c.fetchall():
        wars.append({
            "id": row["id"], "end_time": row["war_end_time"],
            "clan_name": row["clan_name"], "clan_stars": row["clan_stars"],
            "clan_destruction": round(row["clan_destruction"], 1),
            "opponent_name": row["opponent_name"],
            "opponent_stars": row["opponent_stars"],
            "opponent_destruction": round(row["opponent_destruction"], 1),
            "team_size": row["team_size"], "result": row["result"],
            "attack_count": row["attack_count"],
        })

    total_attacks = sum(p["total_attacks"] for p in players)
    avg_stars = round(sum(p["avg_stars"] * p["total_attacks"] for p in players) / total_attacks, 2) if total_attacks else 0
    avg_dest = round(sum(p["avg_destruction"] * p["total_attacks"] for p in players) / total_attacks, 1) if total_attacks else 0

    return {
        "label": f"{MONTH_NAMES[month]} {year}",
        "summary": {
            "total_wars": len(wars),
            "wins": sum(1 for w in wars if w["result"] == "win"),
            "losses": sum(1 for w in wars if w["result"] == "loss"),
            "ties": sum(1 for w in wars if w["result"] == "tie"),
            "total_attacks": total_attacks, "avg_stars": avg_stars, "avg_destruction": avg_dest,
        },
        "players": players, "wars": wars,
    }


def export_cwl_season_csv(conn, year, month, filepath):
    """Write a CSV file for a CWL season."""
    prefix = f"{year}{str(month).zfill(2)}%"
    where = "WHERE w.war_type = 'cwl' AND w.war_end_time LIKE ?"
    params = (prefix,)
    label = f"{MONTH_NAMES[month]} {year}"
    c = conn.cursor()

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Player Performance
        writer.writerow([f"CWL Season: {label} - Player Performance"])
        writer.writerow(["Player", "TH", "Attacks", "Wars", "3-Star%", "2-Star%",
                          "1-Star%", "0-Star%", "Avg Stars", "Avg Destruction%"])
        c.execute(f"""
            SELECT a.attacker_name, MAX(a.attacker_th_level) as th, COUNT(*) as total,
                SUM(CASE WHEN a.stars = 3 THEN 1 ELSE 0 END) as s3,
                SUM(CASE WHEN a.stars = 2 THEN 1 ELSE 0 END) as s2,
                SUM(CASE WHEN a.stars = 1 THEN 1 ELSE 0 END) as s1,
                SUM(CASE WHEN a.stars = 0 THEN 1 ELSE 0 END) as s0,
                ROUND(AVG(a.stars), 2) as avg_stars,
                ROUND(AVG(a.destruction_percentage), 1) as avg_dest,
                COUNT(DISTINCT a.war_id) as wars
            FROM attacks a JOIN wars w ON a.war_id = w.id {where}
            GROUP BY a.attacker_tag ORDER BY avg_stars DESC
        """, params)
        for r in c.fetchall():
            t = r["total"]
            writer.writerow([r["attacker_name"], r["th"], t, r["wars"],
                f"{round(r['s3']/t*100,1)}%", f"{round(r['s2']/t*100,1)}%",
                f"{round(r['s1']/t*100,1)}%", f"{round(r['s0']/t*100,1)}%",
                r["avg_stars"], f"{r['avg_dest']}%"])

        # War Results
        writer.writerow([])
        writer.writerow([f"CWL Season: {label} - War Results"])
        writer.writerow(["Opponent", "Result", "Our Stars", "Their Stars",
                          "Our Destruction%", "Their Destruction%", "Team Size", "Date"])
        c.execute(f"SELECT * FROM wars w {where} ORDER BY w.war_end_time ASC", params)
        for r in c.fetchall():
            end = r["war_end_time"]
            date_str = f"{end[4:6]}/{end[6:8]}/{end[0:4]}" if end else ""
            writer.writerow([r["opponent_name"], r["result"].upper(), r["clan_stars"],
                r["opponent_stars"], f"{round(r['clan_destruction'],1)}%",
                f"{round(r['opponent_destruction'],1)}%",
                f"{r['team_size']}v{r['team_size']}", date_str])

        # Individual Attacks
        writer.writerow([])
        writer.writerow([f"CWL Season: {label} - Individual Attacks"])
        writer.writerow(["War Opponent", "Attacker", "Attacker TH", "Defender",
                          "Defender TH", "Stars", "Destruction%", "Duration"])
        c.execute(f"""
            SELECT a.*, w.opponent_name FROM attacks a JOIN wars w ON a.war_id = w.id
            {where} ORDER BY w.war_end_time ASC, a.attack_order
        """, params)
        for r in c.fetchall():
            dur = r["duration"]
            dur_str = f"{dur//60}:{str(dur%60).zfill(2)}" if dur else ""
            writer.writerow([r["opponent_name"], r["attacker_name"], r["attacker_th_level"],
                r["defender_name"], r["defender_th_level"], _fix_stars(r["stars"], r["destruction_percentage"]),
                f"{r['destruction_percentage']}%", dur_str])


def main():
    if not os.path.exists(DB_PATH):
        print("No war_data.db found. Run war_collector.py first.")
        return

    ensure_dirs()
    conn = get_db()

    # Export per war_type variant (all, regular, cwl)
    for wt in ("all", "regular", "cwl"):
        suffix = f"-{wt}" if wt != "all" else ""
        write_json(os.path.join(DATA_DIR, f"clan-summary{suffix}.json"), export_clan_summary(conn, wt))
        write_json(os.path.join(DATA_DIR, f"player-stats{suffix}.json"), export_player_stats(conn, wt))
        write_json(os.path.join(DATA_DIR, f"war-history{suffix}.json"), export_war_history(conn, wt))
        write_json(os.path.join(DATA_DIR, f"defense-stats{suffix}.json"), export_defense_stats(conn, wt))

    # Export per-war attack details
    c = conn.cursor()
    c.execute("SELECT id FROM wars")
    for row in c.fetchall():
        war_id = row["id"]
        write_json(os.path.join(DATA_DIR, "war", f"{war_id}.json"), export_war_attacks(conn, war_id))

    # Export per-player details
    c.execute("SELECT DISTINCT attacker_tag FROM attacks")
    tags = [row[0] for row in c.fetchall()]
    for tag in tags:
        safe_name = tag.replace("#", "").replace("/", "")
        write_json(os.path.join(DATA_DIR, "player", f"{safe_name}.json"), export_player_detail(conn, tag))

    # Export CWL seasons
    cwl_season_dir = os.path.join(DATA_DIR, "cwl-season")
    os.makedirs(cwl_season_dir, exist_ok=True)
    seasons = export_cwl_seasons(conn)
    write_json(os.path.join(DATA_DIR, "cwl-seasons.json"), seasons)
    for s in seasons:
        y, m = s["year"], s["month"]
        detail = export_cwl_season_detail(conn, y, m)
        write_json(os.path.join(cwl_season_dir, f"{y}-{m}.json"), detail)
        export_cwl_season_csv(conn, y, m, os.path.join(cwl_season_dir, f"{y}-{m}.csv"))
    if seasons:
        print(f"Exported {len(seasons)} CWL season(s)")

    conn.close()

    # Count exported files
    total = sum(len(files) for _, _, files in os.walk(DATA_DIR))
    print(f"Exported {total} files to {DATA_DIR}")


if __name__ == "__main__":
    main()
