"""
Watchlist router — per-user watchlist CRUD endpoints for the Stratum Reasoning Engine.

Endpoints:
  GET /watchlist — returns the authenticated user's watchlist.
    Seeds from watchlist_defaults on first call (zero rows for user).
  PUT /watchlist — replaces the entire watchlist atomically.
    Validates all symbols against TICKER_METADATA, enforces MAX_WATCHLIST_SIZE.

Protected by the require_auth dependency (Supabase JWT).
User identity comes from JWT sub claim (UUID).
Watchlist persists in VPS PostgreSQL (user_watchlist table).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import MetaData, Table, delete, select, text
from sqlalchemy.dialects.postgresql import insert

from reasoning.app.auth import require_auth
from reasoning.app.schemas import WatchlistItem, WatchlistResponse, WatchlistUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum number of tickers allowed per user watchlist
MAX_WATCHLIST_SIZE = 30

# Gold ETF tickers — asset_type "gold_etf"; all others are "equity"
GOLD_TICKERS = {"GLD", "IAU", "SGOL"}

# Static ticker metadata: all VN30 constituents + GLD/IAU/SGOL gold ETFs.
# Validation uses this dict — avoids per-request DB queries for the static universe.
# If a new ticker is added to the DB, update this dict to make it available.
TICKER_METADATA: dict[str, dict] = {
    "GLD": {"name": "SPDR Gold Shares", "asset_type": "gold_etf"},
    "IAU": {"name": "iShares Gold Trust", "asset_type": "gold_etf"},
    "SGOL": {"name": "Aberdeen Physical Gold Shares", "asset_type": "gold_etf"},
    "ACB": {"name": "Asia Commercial Bank", "asset_type": "equity"},
    "BCM": {"name": "Becamex IDC", "asset_type": "equity"},
    "BID": {"name": "BIDV", "asset_type": "equity"},
    "BVH": {"name": "Bao Viet Holdings", "asset_type": "equity"},
    "CTG": {"name": "VietinBank", "asset_type": "equity"},
    "FPT": {"name": "FPT Corporation", "asset_type": "equity"},
    "GAS": {"name": "PV Gas", "asset_type": "equity"},
    "GVR": {"name": "Vietnam Rubber Group", "asset_type": "equity"},
    "HDB": {"name": "HD Bank", "asset_type": "equity"},
    "HPG": {"name": "Hoa Phat Group", "asset_type": "equity"},
    "MBB": {"name": "MB Bank", "asset_type": "equity"},
    "MSN": {"name": "Masan Group", "asset_type": "equity"},
    "MWG": {"name": "Mobile World", "asset_type": "equity"},
    "PLX": {"name": "Petrolimex", "asset_type": "equity"},
    "POW": {"name": "PetroVietnam Power", "asset_type": "equity"},
    "SAB": {"name": "Sabeco", "asset_type": "equity"},
    "SHB": {"name": "SHB Bank", "asset_type": "equity"},
    "SSB": {"name": "SeABank", "asset_type": "equity"},
    "SSI": {"name": "SSI Securities", "asset_type": "equity"},
    "STB": {"name": "Sacombank", "asset_type": "equity"},
    "TCB": {"name": "Techcombank", "asset_type": "equity"},
    "TPB": {"name": "TP Bank", "asset_type": "equity"},
    "VCB": {"name": "Vietcombank", "asset_type": "equity"},
    "VHM": {"name": "Vinhomes", "asset_type": "equity"},
    "VIB": {"name": "VIB Bank", "asset_type": "equity"},
    "VIC": {"name": "Vingroup", "asset_type": "equity"},
    "VJC": {"name": "Vietjet Air", "asset_type": "equity"},
    "VNM": {"name": "Vinamilk", "asset_type": "equity"},
    "VPB": {"name": "VP Bank", "asset_type": "equity"},
    "VRE": {"name": "Vincom Retail", "asset_type": "equity"},
}


def _get_or_seed_watchlist(db_engine, user_id: str) -> list[dict]:
    """Return the user's watchlist items, seeding from defaults if zero rows exist.

    If the user has no rows in user_watchlist, seeds from watchlist_defaults
    using INSERT ... ON CONFLICT DO NOTHING (idempotent) and returns the seeded list.

    Per CONTEXT.md: if zero rows → seed. This means explicitly emptying the watchlist
    will re-seed on next GET (acceptable for v3.0).

    Returns a list of dicts with keys: symbol, name, asset_type.
    """
    metadata = MetaData()
    user_watchlist = Table("user_watchlist", metadata, autoload_with=db_engine)
    watchlist_defaults = Table("watchlist_defaults", metadata, autoload_with=db_engine)

    with db_engine.connect() as conn:
        # Query existing rows for this user
        stmt = select(
            user_watchlist.c.symbol,
            user_watchlist.c.asset_type,
        ).where(user_watchlist.c.user_id == user_id)
        rows = list(conn.execute(stmt))

        if not rows:
            # No rows — seed from defaults
            default_stmt = select(
                watchlist_defaults.c.symbol,
                watchlist_defaults.c.asset_type,
            ).order_by(watchlist_defaults.c.sort_order)
            defaults = list(conn.execute(default_stmt))

            if defaults:
                insert_stmt = insert(user_watchlist).values([
                    {
                        "user_id": user_id,
                        "symbol": row.symbol,
                        "asset_type": row.asset_type,
                    }
                    for row in defaults
                ])
                # ON CONFLICT DO NOTHING — safe if called concurrently
                conn.execute(
                    insert_stmt.on_conflict_do_nothing(
                        index_elements=["user_id", "symbol"]
                    )
                )
                conn.commit()
                rows = defaults

        # Build response list with metadata
        result = []
        for row in rows:
            symbol = row.symbol
            meta = TICKER_METADATA.get(symbol, {})
            result.append({
                "symbol": symbol,
                "name": meta.get("name", symbol),
                "asset_type": meta.get("asset_type", row.asset_type),
            })

    return result


def _validate_symbols(db_engine, symbols: list[str]) -> list[str]:
    """Return list of invalid symbols (not in TICKER_METADATA).

    Uses the static TICKER_METADATA dict — faster than DB queries and
    the ticker universe is static. Any symbol not in the dict is invalid.
    """
    return [s for s in symbols if s not in TICKER_METADATA]


def _replace_watchlist(db_engine, user_id: str, symbols: list[str]) -> None:
    """Atomically replace the user's watchlist with the given list of symbols.

    Deletes all existing rows for user_id, then inserts new rows.
    Caller must validate symbols before calling this function.
    """
    metadata = MetaData()
    user_watchlist = Table("user_watchlist", metadata, autoload_with=db_engine)

    with db_engine.connect() as conn:
        # Delete all existing rows for this user
        conn.execute(
            delete(user_watchlist).where(user_watchlist.c.user_id == user_id)
        )
        # Insert new rows
        if symbols:
            rows = []
            for symbol in symbols:
                meta = TICKER_METADATA.get(symbol, {})
                rows.append({
                    "user_id": user_id,
                    "symbol": symbol,
                    "asset_type": meta.get("asset_type", "equity"),
                })
            conn.execute(insert(user_watchlist).values(rows))
        conn.commit()


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(
    request: Request,
    payload: dict = Depends(require_auth),
) -> WatchlistResponse:
    """Return the authenticated user's watchlist.

    Seeds default tickers (from watchlist_defaults) on first call for a new user.
    """
    user_id = payload["sub"]
    db_engine = request.app.state.db_engine
    tickers = _get_or_seed_watchlist(db_engine, user_id)
    return WatchlistResponse(
        tickers=[
            WatchlistItem(
                symbol=item["symbol"],
                name=item["name"],
                asset_type=item["asset_type"],
            )
            for item in tickers
        ]
    )


@router.put("", status_code=204)
async def put_watchlist(
    body: WatchlistUpdate,
    request: Request,
    payload: dict = Depends(require_auth),
) -> None:
    """Replace the authenticated user's entire watchlist atomically.

    Validates all symbols against the known ticker universe (TICKER_METADATA).
    Enforces a maximum of MAX_WATCHLIST_SIZE tickers.
    An empty list is valid and clears the watchlist.
    """
    if len(body.tickers) > MAX_WATCHLIST_SIZE:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {MAX_WATCHLIST_SIZE} tickers allowed",
        )

    user_id = payload["sub"]
    db_engine = request.app.state.db_engine

    # Validate all symbols before mutating
    invalid = _validate_symbols(db_engine, body.tickers)
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid symbols: {', '.join(sorted(invalid))}",
        )

    _replace_watchlist(db_engine, user_id, body.tickers)
