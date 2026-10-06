from src.common.config import load_companies as _load_companies_config

_config = _load_companies_config()

COMPANIES = {
    ticker: {"name": info["name"], "ir_page": info["ir_page"]}
    for ticker, info in _config["companies"].items()
}
CIK_MAP = {ticker: info["cik"] for ticker, info in _config["companies"].items()}
CASTIFY_FEEDS = {ticker: info["castify_feed"] for ticker, info in _config["companies"].items()}
QUARTERS = _config["quarters"]
