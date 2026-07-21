import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from config import EXPORT_FOLDER

HEADERS = [
    ('文件名', 20),
    ('发票类型', 18),
    ('发票代码', 16),
    ('发票号码', 16),
    ('开票日期', 16),
    ('购买方名称', 30),
    ('购买方税号', 24),
    ('销售方名称', 30),
    ('销售方税号', 24),
    ('金额', 14),
    ('税额', 14),
    ('价税合计', 14),
    ('校验码', 26),
]

FIELD_KEYS = [
    'filename', 'invoice_type', 'invoice_code', 'invoice_number',
    'invoice_date', 'buyer_name', 'buyer_tax_id', 'seller_name',
    'seller_tax_id', 'amount', 'tax_amount', 'total_amount', 'check_code',
]


def export_to_excel(results, filename='发票识别结果.xlsx'):
    wb = Workbook()
    ws = wb.active
    ws.title = '识别结果'

    header_font = Font(name='微软雅黑', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    cell_font = Font(name='微软雅黑', size=10)
    cell_align = Alignment(vertical='center', wrap_text=True)

    for col_idx, (header, width) in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[cell.column_letter].width = width

    ws.freeze_panes = 'A2'

    for row_idx, item in enumerate(results, 2):
        for col_idx, key in enumerate(FIELD_KEYS, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=item.get(key, ''))
            cell.font = cell_font
            cell.alignment = cell_align
            cell.border = thin_border

    filepath = os.path.join(EXPORT_FOLDER, filename)
    wb.save(filepath)
    return filepath
