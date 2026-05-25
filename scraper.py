"""
dira.moch.gov.il Lottery Scraper
Fetches current open lottery projects for young couples (זוג צעיר) and saves to CSV.

Usage:
    python scraper.py           # Fetch, save, print summary
    python scraper.py --debug   # Also print raw API response details
"""

import os
import sys
import json
import urllib.parse

# Fix Hebrew output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
import pandas as pd
from datetime import datetime

# ── Hebrew → English city name mapping ───────────────────────────────────────
CITY_MAP = {
    "תל אביב - יפו": "Tel Aviv-Yafo",
    "תל אביב-יפו": "Tel Aviv-Yafo",
    "תל אביב": "Tel Aviv",
    "ירושלים": "Jerusalem",
    "חיפה": "Haifa",
    "באר שבע": "Beer Sheva",
    "ראשון לציון": "Rishon LeZion",
    "אשדוד": "Ashdod",
    "אשקלון": "Ashkelon",
    "נתניה": "Netanya",
    "פתח תקווה": "Petah Tikva",
    "בני ברק": "Bnei Brak",
    "חולון": "Holon",
    "רמת גן": "Ramat Gan",
    "רחובות": "Rehovot",
    "בת ים": "Bat Yam",
    "כפר סבא": "Kfar Saba",
    "הרצליה": "Herzliya",
    "מודיעין-מכבים-רעות": "Modi'in",
    "מודיעין": "Modi'in",
    "לוד": "Lod",
    "רמלה": "Ramla",
    "עכו": "Acre",
    "נהריה": "Nahariya",
    "טבריה": "Tiberias",
    "צפת": "Safed",
    "דימונה": "Dimona",
    "אילת": "Eilat",
    "קריית גת": "Kiryat Gat",
    "קריית שמונה": "Kiryat Shmona",
    "קריית מלאכי": "Kiryat Malachi",
    "אופקים": "Ofakim",
    "נוף הגליל": "Nof HaGalil",
    "נצרת עילית": "Nof HaGalil",
    "יבנה": "Yavne",
    "טירת כרמל": "Tirat Carmel",
    "עפולה": "Afula",
    "חדרה": "Hadera",
    "כרמיאל": "Karmiel",
    "מגדל העמק": "Migdal HaEmek",
    "נס ציונה": "Nes Ziona",
    "אלעד": "El'ad",
    "מעלה אדומים": "Ma'ale Adumim",
    "ביתר עילית": "Beitar Illit",
    "מודיעין עילית": "Modi'in Illit",
    "אריאל": "Ariel",
    "רעננה": "Ra'anana",
    "כפר יונה": "Kfar Yona",
    "שפרעם": "Shfaram",
    "קריית ביאליק": "Kiryat Bialik",
    "קריית ים": "Kiryat Yam",
    "קריית מוצקין": "Kiryat Motzkin",
    "קריית אתא": "Kiryat Ata",
    "רהט": "Rahat",
    "סח'נין": "Sakhnin",
    "אום אל-פחם": "Umm al-Fahm",
    "בית שמש": "Beit Shemesh",
    "גבעת שמואל": "Givat Shmuel",
    "גדרה": "Gadera",
    "זכרון יעקב": "Zichron Yaakov",
    "אור יהודה": "Or Yehuda",
    "גבעתיים": "Givatayim",
    "רמת השרון": "Ramat HaSharon",
    "הוד השרון": "Hod HaSharon",
    "פרדס חנה-כרכור": "Pardes Hanna-Karkur",
    "טירה": "Tire",
    "כפר קאסם": "Kafr Qasim",
    "שוהם": "Shoham",
    "יהוד-מונוסון": "Yehud",
    "יהוד": "Yehud",
    "קצרין": "Katzrin",
    "מצפה רמון": "Mitzpe Ramon",
    "סדרות": "Sderot",
    "שדרות": "Sderot",
    "נתיבות": "Netivot",
    "ערד": "Arad",
    "קריית ארבע": "Kiryat Arba",
    "מבשרת ציון": "Mevaseret Zion",
    "בית אריה": "Beit Arye",
    "אלפי מנשה": "Alfe Menashe",
    "עמנואל": "Emmanuel",
    "ראש העין": "Rosh HaAyin",
    "פ'תח תקווה": "Petah Tikva",
    "בקה אל-גרביה": "Baqa al-Gharbiyye",
    "טמרה": "Tamra",
    # Cities found in live data
    "כפר מנדא": "Kfar Manda",
    "רכסים": "Raksim",
    "בת חפר": "Bat Hefer",
    "מזכרת בתיה": "Mazkeret Batya",
    "בני עי\"ש": "Bnei Ayish",
    "בית דגן": "Beit Dagan",
    "קדימה-צורן": "Kedima-Zoran",
    "יקנעם עילית": "Yokneam Illit",
    "נהרייה": "Nahariya",
    "קריית עקרון": "Kiryat Ekron",
    "אבן יהודה": "Even Yehuda",
    "גן יבנה": "Gan Yavne",
    "בית שאן": "Beit Shean",
    "עומר": "Omer",
    "להבים": "Lehavim",
    "מיתר": "Meitar",
    "ירוחם": "Yeruham",
    "נתיבות": "Netivot",
    "שדרות": "Sderot",
}

API_BASE = "https://dira.moch.gov.il/api/Invoker"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://dira.moch.gov.il/ProjectsList",
}

# ProjectStatus=4 = active/open, Entitlement=1 = young couple (זוג צעיר)
PROJECT_STATUS = 4
ENTITLEMENT = 1
PAGE_SIZE = 50

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CITIES_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cities_rank.csv")


# ── API helpers ───────────────────────────────────────────────────────────────

def _build_param(page: int) -> str:
    """Build the param string exactly as the Angular app does."""
    return (
        f"?firstApplicantIdentityNumber=&secondApplicantIdentityNumber="
        f"&ProjectStatus={PROJECT_STATUS}&Entitlement={ENTITLEMENT}"
        f"&PageNumber={page}&PageSize={PAGE_SIZE}&"
    )


def _extract_items(raw: dict, debug: bool = False) -> list:
    """Find the project list inside the API response."""
    if debug:
        print(f"  [DEBUG] Response keys: {list(raw.keys())}")
        print(f"  [DEBUG] ActionStatus: {raw.get('ActionStatus')}")

    for key, val in raw.items():
        if isinstance(val, list) and key not in ("Messages",) and len(val) > 0:
            if debug:
                print(f"  [DEBUG] Data array in '{key}': {len(val)} items")
                if val:
                    print(f"  [DEBUG] First item keys: {list(val[0].keys())}")
            return val
    return []


def _coerce_int(val) -> int:
    """Safely convert a value to int, returning 0 on failure."""
    try:
        return int(val) if val not in (None, "", "null") else 0
    except (ValueError, TypeError):
        return 0


def _parse_item(item: dict) -> dict:
    """Normalise one API record to a consistent flat dict."""
    def get(*keys, default=None):
        for k in keys:
            v = item.get(k)
            if v not in (None, ""):
                return v
        return default

    city_heb = get("CityDescription", default="")
    city_eng = CITY_MAP.get(city_heb, city_heb)  # fallback: keep Hebrew as-is

    # LotteryApparmentsNum = total apartments in this lottery draw
    apartments = _coerce_int(get(
        "LotteryApparmentsNum", "TargetHousingUnits", "HousingUnits", default=0
    ))
    registered = _coerce_int(get("TotalSubscribers", default=0))

    # Reserved slots taken out of the general pool
    handicapped_apts  = _coerce_int(get("HousingUnitsForHandicapped", default=0))
    reservist_apts    = _coerce_int(get("HU_Reservists_L", default=0))
    combat_apts       = _coerce_int(get("HU_CombatReservist_L", default=0))
    local_apts        = _coerce_int(get("LocalHousing", default=0))   # בני המקום

    # Subscribers competing only for reserved slots (excluded from general pool)
    handicapped_subs  = _coerce_int(get("TotalHandicappedSubscribers", default=0))
    reservist_subs    = _coerce_int(get("TotalReservedDutySubscribers", default=0))
    combat_subs       = _coerce_int(get("TotalCombatReservistSubscribers", default=0))
    local_subs        = _coerce_int(get("TotalLocalSubscribers", default=0))

    # General pool: what a non-local young couple actually competes for
    general_apts = max(0, apartments - handicapped_apts - reservist_apts - combat_apts - local_apts)
    general_reg  = max(0, registered - handicapped_subs - reservist_subs - combat_subs - local_subs)

    return {
        "city_hebrew":          city_heb,
        "city_english":         city_eng,
        "lottery_number":       get("LotteryNumber", default=""),
        "project_name":         get("ProjectName", "ProcessName", default=""),
        "neighborhood":         get("NeighborhoodName", default=""),
        "contractor":           get("ContractorDescription", default=""),
        "apartments":           apartments,           # total (incl. all reserved)
        "general_apartments":   general_apts,         # non-local general applicants only
        "registered":           registered,           # all subscribers
        "general_registered":   general_reg,          # general-pool subscribers only
        "handicapped_apts":     handicapped_apts,
        "reservist_apts":       reservist_apts,
        "combat_apts":          combat_apts,
        "local_apts":           local_apts,           # בני המקום reserved
        "lottery_date":         get("LotteryDate", default=""),
        "application_end":      get("ApplicationEndDate", default=""),
        "price_per_unit":       get("PricePerUnit", default=""),
        "entitlement":          get("EntitlementDescription", default=""),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_projects(debug: bool = False) -> pd.DataFrame:
    """
    Fetch all currently open young-couple lottery projects.
    Returns a DataFrame with one row per raffle/project.
    """
    all_items: list = []
    page = 1

    while True:
        param_str = _build_param(page)
        request_params = {"method": "Projects", "param": param_str}
        url = API_BASE + "?" + urllib.parse.urlencode(request_params)

        if debug:
            print(f"\n  [DEBUG] GET {url}")

        try:
            resp = requests.get(API_BASE, params=request_params, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f"[ERROR] Network error on page {page}: {e}")
            break

        if debug:
            print(f"  [DEBUG] HTTP {resp.status_code}")

        if resp.status_code != 200:
            print(f"[ERROR] HTTP {resp.status_code} on page {page}")
            if page == 1:
                print(f"  Response: {resp.text[:500]}")
            break

        try:
            raw = resp.json()
        except ValueError:
            print(f"[ERROR] Non-JSON response on page {page}: {resp.text[:300]}")
            break

        action_status = raw.get("ActionStatus")
        # ActionStatus 1 = success for this API (returns data with ProjectItems)
        # 0 or None also treated as success; anything else is a real error
        if action_status not in (0, 1, None, "0", "1", ""):
            err = raw.get("ExceptionMessage") or raw.get("Messages") or ""
            print(f"[WARN] ActionStatus={action_status} on page {page}: {err}")
            if page == 1 and debug:
                print("  Full response:", json.dumps(raw, ensure_ascii=False, indent=2)[:3000])
            # Still try to extract data in case there's something useful
            items = _extract_items(raw, debug)
            if not items:
                break
        else:
            items = _extract_items(raw, debug)

        if not items:
            if page == 1:
                print("[WARN] No data in response. Try running with --debug for details.")
                if debug:
                    print("  Full response:", json.dumps(raw, ensure_ascii=False, indent=2)[:3000])
            break

        all_items.extend(items)
        total_records = raw.get("NumOfRecords") or raw.get("OpenLotteriesCount")
        print(f"  Page {page}: {len(items)} projects (total: {len(all_items)}"
              + (f" of {total_records}" if total_records else "") + ")")

        if len(items) < PAGE_SIZE:
            break  # reached last page
        page += 1

    if not all_items:
        return pd.DataFrame()

    rows = [_parse_item(item) for item in all_items]
    df = pd.DataFrame(rows)
    df["scraped_at"] = datetime.now().isoformat(timespec="seconds")
    return df


def save_data(df: pd.DataFrame) -> tuple:
    """
    Save to data/scraped_YYYYMMDD_HHMMSS.csv and data/latest.csv.
    Returns (timestamped_path, latest_path).
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_path = os.path.join(DATA_DIR, f"scraped_{ts}.csv")
    latest_path = os.path.join(DATA_DIR, "latest.csv")

    df.to_csv(ts_path, index=False, encoding="utf-8-sig")
    df.to_csv(latest_path, index=False, encoding="utf-8-sig")
    return ts_path, latest_path


def generate_cities_csv(df: pd.DataFrame) -> None:
    """
    Create or update cities_rank.csv.
    Creates it fresh if it doesn't exist; adds new cities if it does.
    The preference_rank column is left blank for the user to fill in.
    """
    scraped = (
        df[["city_hebrew", "city_english"]]
        .drop_duplicates()
        .sort_values("city_english")
        .reset_index(drop=True)
    )

    if os.path.exists(CITIES_CSV):
        existing = pd.read_csv(CITIES_CSV, encoding="utf-8-sig")
        # Merge: keep existing ranks, add new cities with empty rank
        merged = scraped.merge(
            existing[["city_hebrew", "preference_rank"]],
            on="city_hebrew",
            how="left"
        )
        new_count = merged["preference_rank"].isna().sum()
        merged.to_csv(CITIES_CSV, index=False, encoding="utf-8-sig")
        if new_count:
            print(f"  Added {new_count} new cities to cities_rank.csv")
        else:
            print(f"  cities_rank.csv up to date ({len(merged)} cities)")
    else:
        scraped["preference_rank"] = ""
        scraped.to_csv(CITIES_CSV, index=False, encoding="utf-8-sig")
        print(f"  Created cities_rank.csv with {len(scraped)} cities.")
        print(f"  --> Fill in the 'preference_rank' column (1-10) before running the notebook.")


def compute_city_probabilities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Core probability calculation using the GENERAL pool only
    (excludes handicapped-reserved and reservist-reserved apartments and their subscribers).

    Returns a DataFrame with one row per city:
      - raffles, total_apartments, general_apartments, total_registered, general_registered
      - p_win: P(winning at least one raffle as a general applicant)
    """
    # Support both old CSVs (no general_apartments column) and new ones
    has_general = "general_apartments" in df.columns

    results = []
    for (city_heb, city_eng), group in df.groupby(["city_hebrew", "city_english"]):
        p_lose_all = 1.0
        for _, row in group.iterrows():
            if has_general:
                apts = row["general_apartments"]
                reg  = row["general_registered"]
            else:
                apts = row["apartments"]
                reg  = row["registered"]

            if reg > 0:
                p_win_raffle = min(1.0, apts / reg)
            elif apts > 0:
                p_win_raffle = 1.0
            else:
                p_win_raffle = 0.0
            p_lose_all *= (1.0 - p_win_raffle)

        results.append({
            "city_hebrew":       city_heb,
            "city_english":      city_eng,
            "raffles":           len(group),
            "total_apartments":  int(group["apartments"].sum()),
            "general_apartments": int(group["general_apartments"].sum()) if has_general else int(group["apartments"].sum()),
            "total_registered":  int(group["registered"].sum()),
            "general_registered": int(group["general_registered"].sum()) if has_general else int(group["registered"].sum()),
            "p_win":             round(1.0 - p_lose_all, 6),
        })

    return (
        pd.DataFrame(results)
        .sort_values("p_win", ascending=False)
        .reset_index(drop=True)
    )


def print_summary(df: pd.DataFrame) -> None:
    """Print a city-level probability summary to stdout."""
    if df.empty:
        print("No data to summarise.")
        return

    city_df = compute_city_probabilities(df)

    print(f"\n{'#':>3}  {'City (English)':<22} {'City (Hebrew)':<22} "
          f"{'Raffles':>7} {'GenApts':>8} {'GenReg':>8} {'P(win)':>8}")
    print("-" * 86)
    for i, row in city_df.iterrows():
        print(
            f"{i+1:>3}  {row['city_english']:<22} {row['city_hebrew']:<22} "
            f"{row['raffles']:>7} {row['general_apartments']:>8} "
            f"{row['general_registered']:>8} {row['p_win']:>8.2%}"
        )

    # Best 3 by pure probability
    top3 = city_df.head(3)
    p_joint = 1.0 - (1 - top3.iloc[0]["p_win"]) * (1 - top3.iloc[1]["p_win"]) * (1 - top3.iloc[2]["p_win"])
    print(f"\nTop 3 cities by probability:")
    for i, row in top3.iterrows():
        print(f"  {i+1}. {row['city_english']} ({row['city_hebrew']}) — P(win) = {row['p_win']:.2%}")
    print(f"  Joint P(win at least one) = {p_joint:.2%}")
    print(f"\nTotal: {len(df)} raffles across {len(city_df)} cities")


def load_all_historical(data_dir: str = DATA_DIR) -> pd.DataFrame:
    """
    Load every timestamped scrape from data_dir into one DataFrame.
    Adds a 'snapshot_time' column (datetime) derived from the filename.
    Returns empty DataFrame if no historical files exist.
    """
    import glob as _glob

    pattern = os.path.join(data_dir, "scraped_*.csv")
    files = sorted(_glob.glob(pattern))
    if not files:
        return pd.DataFrame()

    frames = []
    for path in files:
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
            # Parse timestamp from filename: scraped_YYYYMMDD_HHMMSS.csv
            basename = os.path.splitext(os.path.basename(path))[0]  # scraped_20260525_143000
            ts_str = basename.replace("scraped_", "")               # 20260525_143000
            snapshot_time = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            df["snapshot_time"] = snapshot_time
            frames.append(df)
        except Exception:
            continue  # skip malformed files

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def compute_city_probabilities_over_time(data_dir: str = DATA_DIR) -> pd.DataFrame:
    """
    Load all historical snapshots and compute P(win) per city per snapshot.
    Returns a DataFrame with columns: snapshot_time, city_english, city_hebrew, p_win.
    """
    hist = load_all_historical(data_dir)
    if hist.empty:
        return pd.DataFrame()

    rows = []
    for snapshot_time, snap_df in hist.groupby("snapshot_time"):
        city_probs = compute_city_probabilities(snap_df)
        city_probs["snapshot_time"] = snapshot_time
        rows.append(city_probs)

    return pd.concat(rows, ignore_index=True)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    debug = "--debug" in sys.argv
    print("Fetching lottery projects from dira.moch.gov.il ...")
    df = fetch_projects(debug=debug)

    if df.empty:
        print("\nNo data retrieved. Check your internet connection or run with --debug.")
        sys.exit(1)

    print(f"\nFetched {len(df)} raffle entries.")
    ts_path, latest_path = save_data(df)
    print(f"Saved: {ts_path}")
    print(f"       {latest_path}")
    generate_cities_csv(df)
    print_summary(df)
