import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from config import BASE_DIR

DB_PATH = os.path.join(BASE_DIR, 'data', 'report.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

TRACKED_FIELDS = [
    'invoice_type', 'invoice_code', 'invoice_number', 'invoice_date',
    'buyer_name', 'buyer_tax_id', 'seller_name', 'seller_tax_id',
    'amount', 'tax_amount', 'total_amount', 'check_code',
]


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


@contextmanager
def _db():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS batch (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                total_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                ocr_engine TEXT DEFAULT '',
                detector_model TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS recognition (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                is_success INTEGER NOT NULL DEFAULT 1,
                error_msg TEXT DEFAULT '',
                duration REAL DEFAULT 0,
                invoice_type TEXT DEFAULT '',
                invoice_code TEXT DEFAULT '',
                invoice_number TEXT DEFAULT '',
                invoice_date TEXT DEFAULT '',
                buyer_name TEXT DEFAULT '',
                buyer_tax_id TEXT DEFAULT '',
                seller_name TEXT DEFAULT '',
                seller_tax_id TEXT DEFAULT '',
                amount TEXT DEFAULT '',
                tax_amount TEXT DEFAULT '',
                total_amount TEXT DEFAULT '',
                check_code TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (batch_id) REFERENCES batch(id)
            );

            CREATE TABLE IF NOT EXISTS annotation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                invoice_type TEXT DEFAULT '',
                invoice_code TEXT DEFAULT '',
                invoice_number TEXT DEFAULT '',
                invoice_date TEXT DEFAULT '',
                buyer_name TEXT DEFAULT '',
                buyer_tax_id TEXT DEFAULT '',
                seller_name TEXT DEFAULT '',
                seller_tax_id TEXT DEFAULT '',
                amount TEXT DEFAULT '',
                tax_amount TEXT DEFAULT '',
                total_amount TEXT DEFAULT '',
                check_code TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (batch_id) REFERENCES batch(id)
            );

            CREATE INDEX IF NOT EXISTS idx_recognition_batch ON recognition(batch_id);
            CREATE INDEX IF NOT EXISTS idx_recognition_created ON recognition(created_at);
            CREATE INDEX IF NOT EXISTS idx_annotation_batch ON annotation(batch_id);
        ''')


init_db()


def create_batch(total_count, success_count, ocr_engine='', detector_model=''):
    batch_id = uuid.uuid4().hex[:12]
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    with _db() as conn:
        conn.execute(
            'INSERT INTO batch (id, created_at, total_count, success_count, ocr_engine, detector_model) VALUES (?,?,?,?,?,?)',
            (batch_id, now, total_count, success_count, ocr_engine, detector_model)
        )
    return batch_id


def record_recognition(batch_id, result):
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    is_success = 0 if result.get('error') else 1
    with _db() as conn:
        conn.execute('''
            INSERT INTO recognition
            (batch_id, filename, is_success, error_msg, duration,
             invoice_type, invoice_code, invoice_number, invoice_date,
             buyer_name, buyer_tax_id, seller_name, seller_tax_id,
             amount, tax_amount, total_amount, check_code, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            batch_id,
            result.get('filename', ''),
            is_success,
            result.get('error', ''),
            result.get('duration', 0),
            result.get('invoice_type', ''),
            result.get('invoice_code', ''),
            result.get('invoice_number', ''),
            result.get('invoice_date', ''),
            result.get('buyer_name', ''),
            result.get('buyer_tax_id', ''),
            result.get('seller_name', ''),
            result.get('seller_tax_id', ''),
            result.get('amount', ''),
            result.get('tax_amount', ''),
            result.get('total_amount', ''),
            result.get('check_code', ''),
            now,
        ))


def save_annotations(batch_id, annotations):
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    with _db() as conn:
        for a in annotations:
            conn.execute('''
                INSERT INTO annotation
                (batch_id, filename, invoice_type, invoice_code, invoice_number, invoice_date,
                 buyer_name, buyer_tax_id, seller_name, seller_tax_id,
                 amount, tax_amount, total_amount, check_code, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                batch_id,
                a.get('filename', ''),
                a.get('invoice_type', ''),
                a.get('invoice_code', ''),
                a.get('invoice_number', ''),
                a.get('invoice_date', ''),
                a.get('buyer_name', ''),
                a.get('buyer_tax_id', ''),
                a.get('seller_name', ''),
                a.get('seller_tax_id', ''),
                a.get('amount', ''),
                a.get('tax_amount', ''),
                a.get('total_amount', ''),
                a.get('check_code', ''),
                now,
            ))


def get_overview_stats():
    with _db() as conn:
        row = conn.execute('''
            SELECT
                COUNT(*) as total,
                SUM(is_success) as success,
                AVG(duration) as avg_duration
            FROM recognition
        ''').fetchone()
        total = row['total'] or 0
        success = row['success'] or 0
        avg_dur = round(row['avg_duration'] or 0, 2)
        rate = round(success / total * 100, 1) if total > 0 else 0

        batch_count = conn.execute('SELECT COUNT(*) as c FROM batch').fetchone()['c']

    return {
        'total_images': total,
        'success_count': success,
        'success_rate': rate,
        'avg_duration': avg_dur,
        'batch_count': batch_count,
    }


def get_field_recognition_rates():
    with _db() as conn:
        total = conn.execute('SELECT COUNT(*) as c FROM recognition WHERE is_success=1').fetchone()['c']
        if total == 0:
            return {f: 0 for f in TRACKED_FIELDS}

        rates = {}
        for field in TRACKED_FIELDS:
            row = conn.execute(
                f"SELECT COUNT(*) as c FROM recognition WHERE is_success=1 AND {field} != '' AND {field} IS NOT NULL"
            ).fetchone()
            rates[field] = round(row['c'] / total * 100, 1)
        return rates


def get_invoice_type_distribution():
    with _db() as conn:
        rows = conn.execute('''
            SELECT invoice_type, COUNT(*) as count
            FROM recognition
            WHERE is_success=1 AND invoice_type != ''
            GROUP BY invoice_type
            ORDER BY count DESC
        ''').fetchall()
        return [{'name': r['invoice_type'], 'value': r['count']} for r in rows]


def get_daily_trend(days=30):
    with _db() as conn:
        rows = conn.execute('''
            SELECT
                DATE(created_at) as date,
                COUNT(*) as total,
                SUM(is_success) as success
            FROM recognition
            WHERE created_at >= DATE('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (f'-{days} days',)).fetchall()
        return [{
            'date': r['date'],
            'total': r['total'],
            'success': r['success'] or 0,
        } for r in rows]


def get_engine_comparison():
    with _db() as conn:
        rows = conn.execute('''
            SELECT
                b.ocr_engine,
                COUNT(r.id) as total,
                SUM(r.is_success) as success,
                AVG(r.duration) as avg_duration
            FROM recognition r
            JOIN batch b ON r.batch_id = b.id
            WHERE b.ocr_engine != ''
            GROUP BY b.ocr_engine
        ''').fetchall()
        return [{
            'engine': r['ocr_engine'],
            'total': r['total'],
            'success': r['success'] or 0,
            'rate': round((r['success'] or 0) / r['total'] * 100, 1) if r['total'] > 0 else 0,
            'avg_duration': round(r['avg_duration'] or 0, 2),
        } for r in rows]


def get_annotation_comparison(batch_id=None):
    with _db() as conn:
        if batch_id:
            condition = 'WHERE a.batch_id = ?'
            params = (batch_id,)
        else:
            condition = ''
            params = ()

        rows = conn.execute(f'''
            SELECT r.*, a.id as ann_id,
                a.invoice_type as ann_invoice_type,
                a.invoice_code as ann_invoice_code,
                a.invoice_number as ann_invoice_number,
                a.invoice_date as ann_invoice_date,
                a.buyer_name as ann_buyer_name,
                a.buyer_tax_id as ann_buyer_tax_id,
                a.seller_name as ann_seller_name,
                a.seller_tax_id as ann_seller_tax_id,
                a.amount as ann_amount,
                a.tax_amount as ann_tax_amount,
                a.total_amount as ann_total_amount,
                a.check_code as ann_check_code
            FROM annotation a
            JOIN recognition r ON a.batch_id = r.batch_id AND a.filename = r.filename
            {condition}
        ''', params).fetchall()

        if not rows:
            return {'total': 0, 'correct': 0, 'accuracy': 0, 'field_accuracy': {}, 'details': []}

        total_fields = 0
        correct_fields = 0
        field_stats = {f: {'total': 0, 'correct': 0} for f in TRACKED_FIELDS}
        details = []

        for row in rows:
            row_detail = {'filename': row['filename'], 'fields': {}}
            for field in TRACKED_FIELDS:
                ann_val = (row[f'ann_{field}'] or '').strip()
                rec_val = (row[field] or '').strip()
                if not ann_val:
                    continue
                field_stats[field]['total'] += 1
                total_fields += 1
                is_match = ann_val == rec_val
                if is_match:
                    correct_fields += 1
                    field_stats[field]['correct'] += 1
                row_detail['fields'][field] = {
                    'expected': ann_val,
                    'actual': rec_val,
                    'match': is_match,
                }
            details.append(row_detail)

        field_accuracy = {}
        for f in TRACKED_FIELDS:
            s = field_stats[f]
            field_accuracy[f] = round(s['correct'] / s['total'] * 100, 1) if s['total'] > 0 else None

        return {
            'total': total_fields,
            'correct': correct_fields,
            'accuracy': round(correct_fields / total_fields * 100, 1) if total_fields > 0 else 0,
            'field_accuracy': field_accuracy,
            'details': details,
        }


def get_batch_list(limit=50):
    with _db() as conn:
        rows = conn.execute('''
            SELECT id, created_at, total_count, success_count, ocr_engine, detector_model
            FROM batch ORDER BY created_at DESC LIMIT ?
        ''', (limit,)).fetchall()
        return [dict(r) for r in rows]


def export_report_data():
    overview = get_overview_stats()
    field_rates = get_field_recognition_rates()
    type_dist = get_invoice_type_distribution()
    trend = get_daily_trend(30)
    engine_cmp = get_engine_comparison()
    annotation_cmp = get_annotation_comparison()

    with _db() as conn:
        all_records = conn.execute('''
            SELECT r.*, b.ocr_engine, b.detector_model
            FROM recognition r
            JOIN batch b ON r.batch_id = b.id
            ORDER BY r.created_at DESC
        ''').fetchall()

    return {
        'overview': overview,
        'field_rates': field_rates,
        'type_distribution': type_dist,
        'daily_trend': trend,
        'engine_comparison': engine_cmp,
        'annotation_comparison': annotation_cmp,
        'records': [dict(r) for r in all_records],
    }
