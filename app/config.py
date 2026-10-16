import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# Root .env is the single source of keys; real environment variables still win.
load_dotenv(ROOT / '.env', override=False)
DATA = Path(os.getenv('DATA_DIR') or str(ROOT / '.data')).resolve()
DATABASE_URL = os.getenv('DATABASE_URL') or f'sqlite:///{DATA / "app.db"}'
BRAVE_KEY = os.getenv('BRAVE_SEARCH_API_KEY', '')
BRAVE_STORAGE_RIGHTS = os.getenv('BRAVE_STORAGE_RIGHTS_CONFIRMED', 'false').lower() == 'true'
BRAVE_EXPORT_RIGHTS = os.getenv('BRAVE_EXPORT_RIGHTS_CONFIRMED', 'false').lower() == 'true'
AI_KEY = os.getenv('OPENAI_API_KEY') or os.getenv('AI_API_KEY', '')
AI_MODEL = os.getenv('AI_MODEL', 'gpt-4.1-mini')
HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '8000'))
BRAVE_REQUEST_COST = float(os.getenv('BRAVE_REQUEST_COST_USD', '0.005'))
AI_INPUT_COST = float(os.getenv('AI_INPUT_USD_PER_MILLION', '0.40'))
AI_OUTPUT_COST = float(os.getenv('AI_OUTPUT_USD_PER_MILLION', '1.60'))
EMBEDDED_WORKER = os.getenv('EMBEDDED_WORKER', 'true').lower() == 'true'
APOLLO_KEY = os.getenv('APOLLO_API_KEY', '')
APOLLO_CREDIT_COST = float(os.getenv('APOLLO_CREDIT_COST_USD', '0') or '0')
APOLLO_SEARCH_CREDITS = float(os.getenv('APOLLO_SEARCH_CREDITS', '1'))
APOLLO_ENRICH_CREDITS = float(os.getenv('APOLLO_ENRICH_CREDITS', '1'))
APOLLO_REVEAL_CREDITS = float(os.getenv('APOLLO_REVEAL_CREDITS', '1'))
APOLLO_STORAGE_RIGHTS = os.getenv('APOLLO_STORAGE_RIGHTS_CONFIRMED', 'false').lower() == 'true'
APOLLO_EXPORT_RIGHTS = os.getenv('APOLLO_EXPORT_RIGHTS_CONFIRMED', 'false').lower() == 'true'
APOLLO_CALLS_PER_HOUR = int(os.getenv('APOLLO_CALLS_PER_HOUR', '600'))
APOLLO_PER_SECOND = float(os.getenv('APOLLO_MIN_INTERVAL_SECONDS', '6'))
DEFAULT_SEARCH_BUDGET = 10
DEFAULT_MONTHLY_BUDGET = 100
DEFAULT_SETTINGS = {'monthly_budget': DEFAULT_MONTHLY_BUDGET, 'search_budget': DEFAULT_SEARCH_BUDGET, 'evaluation_budget': 0.25}
MAX_UPLOAD = 10 * 1024 * 1024
MAX_DOCUMENTS = 10
MAX_AI_CHARS = 80000


def initialize_data():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    (DATA / 'documents').mkdir(exist_ok=True, mode=0o700)

for price in [BRAVE_REQUEST_COST, AI_INPUT_COST, AI_OUTPUT_COST, APOLLO_CREDIT_COST, APOLLO_SEARCH_CREDITS, APOLLO_ENRICH_CREDITS, APOLLO_REVEAL_CREDITS, APOLLO_PER_SECOND]:
    import math
    if not math.isfinite(price) or price < 0: raise ValueError('Provider prices must be finite and nonnegative.')

if not 1 <= APOLLO_CALLS_PER_HOUR <= 600: raise ValueError('Apollo hourly limit must be between 1 and 600.')
