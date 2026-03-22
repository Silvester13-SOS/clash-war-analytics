"""
Clash of Clans War Data Collector
Polls the current war (and CWL) via coc.py and stores all attack data in SQLite.
Run this after each war ends to build your historical dataset.
"""
import asyncio
import coc
import sqlite3
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "war_data.db")
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "war_collector.log")

# --- Logging setup ---
logger = logging.getLogger("war_collector")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(_fmt)
_fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(_fmt)
logger.addHandler(_ch)
logger.addHandler(_fh)


def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()


def war_exists(end_time):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, result FROM wars WHERE war_end_time = ?", (end_time,))
    result = c.fetchone()
    conn.close()
    return result


def delete_war(war_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM attacks WHERE war_id = ?", (war_id,))
        conn.execute("DELETE FROM defenses WHERE war_id = ?", (war_id,))
        conn.execute("DELETE FROM wars WHERE id = ?", (war_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_war(war_data, attacks_data, defenses_data=None):
    collected_at = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("BEGIN")
        c = conn.cursor()
        c.execute("""INSERT INTO wars (war_end_time, clan_tag, clan_name, clan_stars,
                    clan_destruction, opponent_tag, opponent_name, opponent_stars,
                    opponent_destruction, team_size, attacks_per_member, result, war_type,
                    collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (*war_data, collected_at))
        war_id = c.lastrowid
        for attack in attacks_data:
            c.execute("""INSERT INTO attacks (war_id, attacker_tag, attacker_name,
                        attacker_th_level, attacker_map_position, defender_tag,
                        defender_name, defender_th_level, defender_map_position,
                        stars, destruction_percentage, attack_order, duration)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (war_id, *attack))
        for defense in (defenses_data or []):
            c.execute("""INSERT INTO defenses (war_id, defender_tag, defender_name,
                        defender_th_level, defender_map_position, attacker_tag,
                        attacker_name, attacker_th_level, stars_received,
                        destruction_received, attack_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (war_id, *defense))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return war_id


def determine_result(our_stars, their_stars, our_dest, their_dest):
    if our_stars > their_stars:
        return "win"
    elif our_stars < their_stars:
        return "loss"
    else:
        if our_dest > their_dest:
            return "win"
        elif our_dest < their_dest:
            return "loss"
        return "tie"


def build_member_lookup(clan_members, opponent_members):
    lookup = {}
    for member in clan_members:
        lookup[member.tag] = {
            "name": member.name,
            "th_level": member.town_hall,
            "map_position": member.map_position,
        }
    for member in opponent_members:
        lookup[member.tag] = {
            "name": member.name,
            "th_level": member.town_hall,
            "map_position": member.map_position,
        }
    return lookup


def validate_stars(stars, destruction):
    """Enforce Clash of Clans star rules based on destruction percentage.
    - 100% destruction always = 3 stars
    - >=50% destruction = at least 1 star
    """
    if destruction >= 100:
        return 3
    if destruction >= 50 and stars < 1:
        return 1
    return stars


def extract_attacks(members, member_lookup, attacks_per_member=2):
    attacks_data = []
    for member in members:
        actual_attacks = member.attacks or []
        for attack in actual_attacks:
            attacker = member_lookup.get(attack.attacker_tag, {})
            defender = member_lookup.get(attack.defender_tag, {})
            stars = validate_stars(attack.stars, attack.destruction)
            attacks_data.append((
                attack.attacker_tag,
                attacker.get("name", "Unknown"),
                attacker.get("th_level", 0),
                attacker.get("map_position", 0),
                attack.defender_tag,
                defender.get("name", "Unknown"),
                defender.get("th_level", 0),
                defender.get("map_position", 0),
                stars,
                attack.destruction,
                attack.order,
                getattr(attack, "duration", 0),
            ))
        # Add 0-star records for each missed attack
        missed = attacks_per_member - len(actual_attacks)
        for _ in range(missed):
            info = member_lookup.get(member.tag, {})
            attacks_data.append((
                member.tag,
                info.get("name", member.name),
                info.get("th_level", member.town_hall),
                info.get("map_position", member.map_position),
                "",       # no defender tag
                "Missed", # defender name placeholder
                0,        # defender th level
                0,        # defender map position
                0,        # 0 stars
                0.0,      # 0% destruction
                0,        # no attack order
                0,        # no duration
            ))
    return attacks_data


def extract_defenses(our_members, opponent_members, member_lookup):
    """Extract attacks made BY the opponent AGAINST our bases."""
    defenses_data = []
    for opp_member in opponent_members:
        if not opp_member.attacks:
            continue
        for attack in opp_member.attacks:
            # Only include attacks targeting our clan's members
            defender = member_lookup.get(attack.defender_tag, {})
            attacker = member_lookup.get(attack.attacker_tag, {})
            # Check if the defender is one of our members
            our_tags = {m.tag for m in our_members}
            if attack.defender_tag in our_tags:
                stars = validate_stars(attack.stars, attack.destruction)
                defenses_data.append((
                    attack.defender_tag,
                    defender.get("name", "Unknown"),
                    defender.get("th_level", 0),
                    defender.get("map_position", 0),
                    attack.attacker_tag,
                    attacker.get("name", "Unknown"),
                    attacker.get("th_level", 0),
                    stars,
                    attack.destruction,
                    attack.order,
                ))
    return defenses_data


async def retry_async(coro_func, *args, retries=3, delay=2, label="API call"):
    """Retry an async call up to `retries` times with exponential back-off."""
    for attempt in range(1, retries + 1):
        try:
            return await coro_func(*args)
        except (coc.PrivateWarLog, coc.NotFound, coc.InvalidCredentials):
            raise  # don't retry non-transient errors
        except Exception as e:
            if attempt == retries:
                logger.error("%s failed after %d attempts: %s", label, retries, e)
                raise
            logger.warning("%s attempt %d/%d failed: %s – retrying in %ds",
                           label, attempt, retries, e, delay * attempt)
            await asyncio.sleep(delay * attempt)


async def collect_current_war(client, clan_tag):
    try:
        war = await retry_async(client.get_current_war, clan_tag,
                                label="get_current_war")
    except coc.PrivateWarLog:
        logger.warning("War log is set to private. Cannot access war data.")
        return
    except coc.NotFound:
        logger.error("Clan not found.")
        return
    except Exception as e:
        logger.error("Failed to fetch current war: %s", e)
        return

    if war is None or war.state == "notInWar":
        logger.info("Clan is not currently in a war.")
        return

    if war.state == "preparation":
        logger.info("War is in preparation phase. No attacks to collect yet.")
        return

    end_time = war.end_time.raw_time
    existing = war_exists(end_time)

    if existing and war.state == "warEnded" and existing[1] != "in_progress":
        logger.info("War ending %s already fully recorded. Skipping.", end_time)
        return

    # Delete existing partial/in-progress data to re-save with latest
    if existing:
        logger.info("Updating war data for %s...", end_time)
        delete_war(existing[0])

    if war.state == "warEnded":
        result = determine_result(
            war.clan.stars, war.opponent.stars,
            war.clan.destruction, war.opponent.destruction
        )
    else:
        result = "in_progress"

    attacks_per_member = getattr(war, "attacks_per_member", 2)
    # CWL wars have 1 attack per member; detect and label correctly
    war_type = "cwl" if attacks_per_member == 1 else "regular"

    war_data = (
        end_time,
        war.clan.tag,
        war.clan.name,
        war.clan.stars,
        war.clan.destruction,
        war.opponent.tag,
        war.opponent.name,
        war.opponent.stars,
        war.opponent.destruction,
        war.team_size,
        attacks_per_member,
        result,
        war_type,
    )

    member_lookup = build_member_lookup(war.clan.members, war.opponent.members)
    attacks_data = extract_attacks(war.clan.members, member_lookup, attacks_per_member)
    defenses_data = extract_defenses(war.clan.members, war.opponent.members, member_lookup)

    war_id = save_war(war_data, attacks_data, defenses_data)
    label = "CWL" if war_type == "cwl" else "Regular War"
    logger.info("[%s] Saved vs %s | %d attacks | %d defenses | %s",
                label, war.opponent.name, len(attacks_data), len(defenses_data), result.upper())
    logger.info("  Stars: %d-%d | Destruction: %.1f%%-%.1f%%",
                war.clan.stars, war.opponent.stars,
                war.clan.destruction, war.opponent.destruction)


async def collect_cwl(client, clan_tag):
    try:
        league_group = await retry_async(client.get_league_group, clan_tag,
                                         label="get_league_group")
    except Exception as e:
        logger.info("No CWL data available: %s", e)
        return

    saved_count = 0

    for rnd in league_group.rounds:
        # Each round contains war tags — try both iteration patterns
        war_tags = getattr(rnd, "war_tags", None) or list(rnd)
        for war_tag in war_tags:
            if str(war_tag) == "#0":
                continue
            try:
                war = await retry_async(client.get_league_war, war_tag,
                                        label=f"get_league_war({war_tag})")
            except Exception as e:
                logger.warning("  Could not fetch CWL war %s: %s", war_tag, e)
                continue

            if war.state == "notInWar":
                continue

            # Only process wars involving our clan
            our_clan, their_clan = None, None
            if war.clan.tag == clan_tag:
                our_clan, their_clan = war.clan, war.opponent
            elif war.opponent.tag == clan_tag:
                our_clan, their_clan = war.opponent, war.clan
            else:
                continue

            end_time = war.end_time.raw_time
            existing = war_exists(end_time)

            if existing and war.state == "warEnded" and existing[1] != "in_progress":
                continue
            if existing:
                delete_war(existing[0])

            if war.state == "warEnded":
                result = determine_result(
                    our_clan.stars, their_clan.stars,
                    our_clan.destruction, their_clan.destruction
                )
            else:
                result = "in_progress"

            war_data = (
                end_time,
                our_clan.tag, our_clan.name, our_clan.stars, our_clan.destruction,
                their_clan.tag, their_clan.name, their_clan.stars, their_clan.destruction,
                war.team_size,
                1,  # CWL is always 1 attack per member
                result,
                "cwl",
            )

            member_lookup = build_member_lookup(war.clan.members, war.opponent.members)
            attacks_data = extract_attacks(our_clan.members, member_lookup, 1)
            defenses_data = extract_defenses(our_clan.members, their_clan.members, member_lookup)

            save_war(war_data, attacks_data, defenses_data)
            saved_count += 1
            logger.info("  [CWL] Saved vs %s | %d attacks | %d defenses | %s",
                        their_clan.name, len(attacks_data), len(defenses_data), result.upper())

    logger.info("CWL collection done. %d wars saved.", saved_count)


async def collect_player_profiles(client):
    """Fetch hero and equipment data for every player in the attacks table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT attacker_tag FROM attacks")
    tags = [row[0] for row in c.fetchall()]
    conn.close()

    if not tags:
        logger.info("No players to fetch profiles for.")
        return

    logger.info("Fetching profiles for %d players...", len(tags))
    fetched = 0

    for tag in tags:
        try:
            player = await client.get_player(tag)
        except Exception as e:
            logger.warning("  Could not fetch %s: %s", tag, e)
            continue

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Save heroes
        for hero in getattr(player, "heroes", []):
            if getattr(hero, "is_home_base", True):
                c.execute("""INSERT INTO player_heroes (player_tag, hero_name, hero_level, max_level)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(player_tag, hero_name)
                            DO UPDATE SET hero_level=excluded.hero_level, max_level=excluded.max_level""",
                          (tag, hero.name, hero.level, hero.max_level))

        # Save equipment
        for equip in getattr(player, "equipment", []):
            hero_name = getattr(equip, "hero", None) or "Unknown"
            if not isinstance(hero_name, str):
                hero_name = str(hero_name)
            c.execute("""INSERT INTO player_equipment (player_tag, equipment_name, equipment_level, max_level, hero_name)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(player_tag, equipment_name)
                        DO UPDATE SET equipment_level=excluded.equipment_level, max_level=excluded.max_level, hero_name=excluded.hero_name""",
                      (tag, equip.name, equip.level, equip.max_level, hero_name))

        conn.commit()
        conn.close()
        fetched += 1

    logger.info("Fetched %d/%d player profiles.", fetched, len(tags))


def finalize_stale_wars():
    """Auto-finalize wars stuck as 'in_progress' whose end_time has passed.

    If the API no longer has the war data, we determine the result from whatever
    attack data we collected while the war was live.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.000Z")

    c.execute("""SELECT id, war_end_time, clan_stars, clan_destruction,
                        opponent_stars, opponent_destruction, opponent_name
                 FROM wars WHERE result = 'in_progress'""")
    stale = c.fetchall()

    for row in stale:
        war_id, end_time, clan_stars, clan_dest, opp_stars, opp_dest, opp_name = row
        # Compare end_time with now (format: 20260303T233901.000Z)
        if end_time and end_time < now:
            result = determine_result(clan_stars, opp_stars, clan_dest, opp_dest)
            c.execute("UPDATE wars SET result = ? WHERE id = ?", (result, war_id))
            logger.info("Finalized stale war id=%d vs %s as %s (stars %d-%d)",
                        war_id, opp_name, result.upper(), clan_stars, opp_stars)

    conn.commit()
    conn.close()


def verify_data():
    """Post-collection verification: log warnings for incomplete data."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM wars")
    war_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM attacks")
    attack_count = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT player_tag) FROM player_heroes")
    profile_count = c.fetchone()[0]

    logger.info("=== Database: %d wars | %d attacks | %d player profiles ===",
                war_count, attack_count, profile_count)

    # Check for stale in-progress wars
    c.execute("SELECT id, war_end_time, opponent_name, collected_at FROM wars WHERE result = 'in_progress'")
    stale = c.fetchall()
    for row in stale:
        logger.warning("War id=%d vs %s (ends %s) still marked in_progress (collected %s)",
                        row[0], row[2], row[1], row[3])

    # Check for wars with fewer attacks than expected
    c.execute("""SELECT w.id, w.opponent_name, w.team_size, w.attacks_per_member,
                        COUNT(a.id) as attack_count
                 FROM wars w
                 LEFT JOIN attacks a ON a.war_id = w.id
                 GROUP BY w.id""")
    for row in c.fetchall():
        war_id, opp_name, team_size, apm, actual = row
        expected = team_size * apm
        if actual < expected:
            logger.warning("War id=%d vs %s has %d/%d expected attacks",
                           war_id, opp_name, actual, expected)

    conn.close()


async def main():
    clan_tag = os.getenv("CLAN_TAG", "#822URC")
    email = os.getenv("COC_EMAIL")
    password = os.getenv("COC_PASSWORD")

    if not email or not password:
        logger.error("Set COC_EMAIL and COC_PASSWORD in your .env file")
        return

    init_db()

    client = coc.Client(key_count=1, key_names="war-tracker")

    try:
        await client.login(email, password)
        logger.info("Logged in. Collecting war data for %s...", clan_tag)

        # Cache clan metadata (badge, level, war wins)
        try:
            clan = await client.get_clan(clan_tag)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""INSERT INTO clan_meta (clan_tag, clan_name, badge_url, clan_level, war_wins, win_streak)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(clan_tag) DO UPDATE SET
                        clan_name=excluded.clan_name, badge_url=excluded.badge_url,
                        clan_level=excluded.clan_level, war_wins=excluded.war_wins, win_streak=excluded.win_streak""",
                      (clan_tag, clan.name, clan.badge.medium, clan.level, clan.war_wins, clan.war_win_streak))
            conn.commit()
            conn.close()
            logger.info("Clan: %s | Level %d | %d war wins", clan.name, clan.level, clan.war_wins)
        except Exception as e:
            logger.warning("Could not fetch clan info: %s", e)

        logger.info("--- Current/Recent War ---")
        await collect_current_war(client, clan_tag)

        logger.info("--- Clan War League ---")
        await collect_cwl(client, clan_tag)

        logger.info("--- Player Profiles (Heroes & Equipment) ---")
        await collect_player_profiles(client)

        # Finalize any wars stuck as in_progress whose end time has passed
        finalize_stale_wars()

        # Summary & verification
        verify_data()

    except coc.InvalidCredentials:
        logger.error("Invalid developer portal credentials. Check your .env file.")
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
