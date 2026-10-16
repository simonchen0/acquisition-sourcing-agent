import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv('DATA_DIR', str(ROOT / '.data'))).resolve()
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA / "app.db"}')
BRAVE_KEY = os.getenv('BRAVE_SEARCH_API_KEY', '')
BRAVE_STORAGE_RIGHTS = os.getenv('BRAVE_STORAGE_RIGHTS_CONFIRMED', 'false').lower() == 'true'
BRAVE_EXPORT_RIGHTS = os.getenv('BRAVE_EXPORT_RIGHTS_CONFIRMED', 'false').lower() == 'true'
AI_KEY = os.getenv('AI_API_KEY') or os.getenv('OPENAI_API_KEY', '')
AI_MODEL = os.getenv('AI_MODEL', 'gpt-4.1-mini')
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'true').lower() == 'true'
BRAVE_REQUEST_COST = float(os.getenv('BRAVE_REQUEST_COST_USD', '0.005'))
AI_INPUT_COST = float(os.getenv('AI_INPUT_USD_PER_MILLION', '0.40'))
AI_OUTPUT_COST = float(os.getenv('AI_OUTPUT_USD_PER_MILLION', '1.60'))
MAX_UPLOAD = 10 * 1024 * 1024
MAX_DOCUMENTS = 10
MAX_AI_CHARS = 80000


def initialize_data():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    (DATA / 'documents').mkdir(exist_ok=True, mode=0o700)

for price in [BRAVE_REQUEST_COST, AI_INPUT_COST, AI_OUTPUT_COST]:
    import math
    if not math.isfinite(price) or price < 0: raise ValueError('Provider prices must be finite and nonnegative.')
