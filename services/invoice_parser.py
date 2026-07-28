import re


def parse_invoice(ocr_items, full_text):
    result = {
        'invoice_type': _extract_invoice_type(full_text),
        'invoice_code': _extract_invoice_code(full_text),
        'invoice_number': _extract_invoice_number(full_text),
        'invoice_date': _extract_date(full_text),
        'buyer_name': '',
        'buyer_tax_id': '',
        'seller_name': '',
        'seller_tax_id': '',
        'amount': '',
        'tax_amount': '',
        'total_amount': '',
        'check_code': _extract_check_code(full_text),
    }

    _extract_buyer_seller(full_text, ocr_items, result)
    _extract_amounts(full_text, ocr_items, result)

    return result


def _extract_invoice_type(text):
    type_patterns = [
        (r'增值税电子专用发票', '增值税电子专用发票'),
        (r'增值税电子普通发票', '增值税电子普通发票'),
        (r'增值税专用发票', '增值税专用发票'),
        (r'增值税普通发票', '增值税普通发票'),
        (r'电子发票[（(]增值税专用发票[)）]', '全电发票(专用)'),
        (r'电子发票[（(]普通发票?[)）]', '全电发票(普通)'),
        (r'数电票', '全电发票'),
        (r'电子[普晋昔]?通发票', '增值税电子普通发票'),  # 兼容"普"被误识别
        (r'电子发票', '电子发票'),
        (r'通发票', '增值税普通发票'),  # 标题只识别出尾部时的兑底
    ]
    for pattern, name in type_patterns:
        if re.search(pattern, text):
            return name
    return '未知类型'


def _extract_invoice_code(text):
    m = re.search(r'发票代码[：:\s]*(\d{10,12})', text)
    if m:
        return m.group(1)
    m = re.search(r'代码[：:\s]*(\d{10,12})', text)
    return m.group(1) if m else ''


def _extract_invoice_number(text):
    m = re.search(r'发票号码[：:\s]*(\d{8,20})', text)
    if m:
        return m.group(1)
    m = re.search(r'号码[：:\s]*(\d{8,20})', text)
    if m:
        return m.group(1)
    m = re.search(r'数电票号码[：:\s]*(\d{20})', text)
    return m.group(1) if m else ''


def _extract_date(text):
    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
    if m:
        return f"{m.group(1)}年{m.group(2).zfill(2)}月{m.group(3).zfill(2)}日"
    m = re.search(r'开票日期[：:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})', text)
    return m.group(1) if m else ''


def _extract_check_code(text):
    m = re.search(r'校[验]?\s*码[：:\s]*(\d{20})', text)
    if m:
        return m.group(1)
    m = re.search(r'校[验]?\s*码[：:\s]*(\d[\d\s]{18,}\d)', text)
    if m:
        return re.sub(r'\s', '', m.group(1))
    return ''


# 中文与字母数字之间 \b 不成立（中文属于 \w），改用显式 lookaround 界定边界
TAX_ID_STRICT = re.compile(r'(?<![0-9A-Za-z])([0-9A-HJ-NPQRTUWXY]{18})(?![0-9A-Za-z])')
TAX_ID_LOOSE = re.compile(r'(?<![0-9A-Za-z])([0-9A-Z]{15,20})(?![0-9A-Za-z])')


def _extract_buyer_seller(full_text, ocr_items, result):
    """基于 OCR 坐标定位购买方 / 销售方的名称与税号，兼容左右版式与上下版式。"""
    buyer_kw, seller_kw = _locate_party_keywords(ocr_items)
    tax_candidates = _collect_tax_id_candidates(ocr_items, result)

    _assign_tax_ids(tax_candidates, buyer_kw, seller_kw, result)
    _assign_party_names(ocr_items, buyer_kw, seller_kw, result)

    # 文本正则兜底
    if not result['buyer_name']:
        m = re.search(r'购[买货]?\s*方.*?(?<!服务)名\s*称[：:\s]*([^\n]+)', full_text, re.DOTALL)
        if m:
            result['buyer_name'] = _clean_name(m.group(1))
    if not result['seller_name']:
        m = re.search(r'销[售货]?\s*方.*?(?<!服务)名\s*称[：:\s]*([^\n]+)', full_text, re.DOTALL)
        if m:
            result['seller_name'] = _clean_name(m.group(1))

    if not result['buyer_tax_id'] or not result['seller_tax_id']:
        # 全文兑底：忽略已识别为发票号码 / 校验码的数字串（含其截断片段）
        used = {result.get('invoice_number', ''), result.get('invoice_code', ''),
                result.get('check_code', ''),
                result.get('buyer_tax_id', ''), result.get('seller_tax_id', '')}
        used_texts = [u for u in used if u]
        tail = [t for t in TAX_ID_LOOSE.findall(full_text)
                if t not in used and 15 <= len(t) <= 20
                and not any(t != u and t in u for u in used_texts)]
        # 优先 18 位统一社会信用代码
        tail.sort(key=lambda s: (0 if len(s) == 18 else 1, -sum(c.isalpha() for c in s)))
        for tid in tail:
            if tid in (result['buyer_tax_id'], result['seller_tax_id']):
                continue
            slot = _nearest_party_slot(tid, ocr_items, buyer_kw, seller_kw, result)
            if slot:
                result[slot] = tid
            if result['buyer_tax_id'] and result['seller_tax_id']:
                break


def _nearest_party_slot(tid, ocr_items, buyer_kw, seller_kw, result):
    """按候选税号所在 item 与购/销方锚点的距离决定归属，锚点缺失时按空位顺序填。"""
    host = None
    for it in ocr_items:
        if tid in re.sub(r'[\s:：]', '', it['text']):
            host = it
            break
    if host is not None and (buyer_kw or seller_kw):
        def d(anchor):
            if anchor is None:
                return float('inf')
            return abs(host['x'] - anchor['x']) + abs(host['y'] - anchor['y']) * 1.2

        prefer = 'buyer_tax_id' if d(buyer_kw) <= d(seller_kw) else 'seller_tax_id'
        if not result[prefer]:
            return prefer
        other = 'seller_tax_id' if prefer == 'buyer_tax_id' else 'buyer_tax_id'
        return other if not result[other] else None
    if not result['buyer_tax_id']:
        return 'buyer_tax_id'
    if not result['seller_tax_id']:
        return 'seller_tax_id'
    return None


def _locate_party_keywords(ocr_items):
    """返回购买方 / 销售方标签所在的 item（若存在）。"""
    buyer_kw = None
    seller_kw = None
    for it in ocr_items:
        text = re.sub(r'\s', '', it['text'])
        if buyer_kw is None and re.search(r'购买方|购货方|购方|购买', text):
            buyer_kw = it
        if seller_kw is None and re.search(r'销售方|销货方|销方|销售', text):
            seller_kw = it
    return buyer_kw, seller_kw


def _collect_tax_id_candidates(ocr_items, result):
    """从 OCR items 里筛出可能是税号的候选（18 位统一社会信用代码优先）。"""
    exclude = {result.get('invoice_number', ''), result.get('invoice_code', ''),
               result.get('check_code', '')}
    candidates = []
    for it in ocr_items:
        raw = re.sub(r'[\s:：]', '', it['text'])
        # 剔除明显的标签行
        if re.search(r'发票号码|发票代码|校验码|数电票号码', it['text']):
            continue
        # 严格 18 位
        for m in TAX_ID_STRICT.finditer(raw):
            tid = m.group(1)
            if tid in exclude:
                continue
            # 至少包含 1 位字母，或以 91/92 等常见开头（企业统一信用代码）
            if not (any(c.isalpha() for c in tid) or re.match(r'9[12]\d', tid) or re.match(r'\d{18}', tid)):
                continue
            candidates.append({'item': it, 'value': tid, 'strict': True})
        if not candidates or candidates[-1]['item'] is not it:
            # 宽松 15-20 位
            for m in TAX_ID_LOOSE.finditer(raw):
                tid = m.group(1)
                if tid in exclude or len(tid) < 15:
                    continue
                # 避免与严格结果重复
                if any(c['value'] == tid for c in candidates):
                    continue
                # 全数字且不足 18 位大概率是号码，跳过
                if tid.isdigit() and len(tid) != 18:
                    continue
                candidates.append({'item': it, 'value': tid, 'strict': False})
    return candidates


def _assign_tax_ids(candidates, buyer_kw, seller_kw, result):
    if not candidates:
        return

    def _dist(item, anchor):
        if anchor is None:
            return float('inf')
        return abs(item['x'] - anchor['x']) + abs(item['y'] - anchor['y']) * 1.2

    # 同一税号可能重复出现（如盖章处），去重后只剩一个值时按锚点归属单侧
    if len({c['value'] for c in candidates}) == 1:
        c = candidates[0]
        target = 'buyer_tax_id'
        if buyer_kw or seller_kw:
            best_b = min(_dist(x['item'], buyer_kw) for x in candidates)
            best_s = min(_dist(x['item'], seller_kw) for x in candidates)
            if best_s < best_b:
                target = 'seller_tax_id'
        result[target] = c['value']
        return

    # 位置策略：优先看两者是否横向排列（y 相近）
    top_two = sorted(candidates, key=lambda c: (c['item']['y'], c['item']['x']))[:2]
    y_gap = abs(top_two[0]['item']['y'] - top_two[1]['item']['y'])

    if y_gap < 40:
        # 横向：x 小的是买方，x 大的是卖方
        left, right = sorted(top_two, key=lambda c: c['item']['x'])
        result['buyer_tax_id'] = left['value']
        result['seller_tax_id'] = right['value']
    else:
        # 纵向：y 小的（靠上）是买方，y 大的（靠下）是卖方
        top, bottom = sorted(top_two, key=lambda c: c['item']['y'])
        result['buyer_tax_id'] = top['value']
        result['seller_tax_id'] = bottom['value']

    # 如果找到了关键字，用关键字锚点校正
    if buyer_kw and seller_kw:
        b_val, s_val = _match_by_anchor(candidates, buyer_kw, seller_kw)
        if b_val:
            result['buyer_tax_id'] = b_val
        if s_val:
            result['seller_tax_id'] = s_val


def _match_by_anchor(candidates, buyer_kw, seller_kw):
    def dist(item, anchor):
        return abs(item['x'] - anchor['x']) + abs(item['y'] - anchor['y']) * 1.2

    buyer_best = min(candidates, key=lambda c: dist(c['item'], buyer_kw))
    seller_best = min(candidates, key=lambda c: dist(c['item'], seller_kw))
    if buyer_best is seller_best or buyer_best['value'] == seller_best['value']:
        return None, None
    return buyer_best['value'], seller_best['value']


def _assign_party_names(ocr_items, buyer_kw, seller_kw, result):
    """根据坐标就近原则填充购/销方名称。"""
    name_items = []
    for it in ocr_items:
        m = re.search(r'名\s*称[：:\s]*(.+)', it['text'])
        if m is None:
            # 竖排"名称"被拆块后，值 item 常以"称："开头
            m = re.match(r'称\s*[：:]\s*(.+)', it['text'].strip())
        if m:
            value = _clean_name(m.group(1))
            if value:
                name_items.append((it, value))
            continue
        # 有些发票"名称:"与公司名不在同一 item；竖排标签还可能被拆成"名"/"称："两块
        if re.fullmatch(r'名\s*称[：:]?|称[：:]|名', it['text'].strip()):
            near = _find_neighbor_text(ocr_items, it)
            if near:
                value = _clean_name(near)
                if value:
                    name_items.append((it, value))

    if not name_items:
        return

    def dist(item, anchor):
        if anchor is None:
            return float('inf')
        return abs(item['x'] - anchor['x']) + abs(item['y'] - anchor['y']) * 1.2

    if buyer_kw and not result['buyer_name']:
        best = min(name_items, key=lambda p: dist(p[0], buyer_kw))
        if dist(best[0], buyer_kw) < 400:
            result['buyer_name'] = best[1]
    if seller_kw and not result['seller_name']:
        best = min(name_items, key=lambda p: dist(p[0], seller_kw))
        if dist(best[0], seller_kw) < 400 and best[1] != result.get('buyer_name'):
            result['seller_name'] = best[1]


def _find_neighbor_text(ocr_items, anchor):
    """寻找 anchor 右侧或下方最近的一段疑似名称文本。"""
    best = None
    best_dist = float('inf')
    for it in ocr_items:
        if it is anchor:
            continue
        if re.search(r'名\s*称|纳税人|识别号|别号|税号|地\s*址|电\s*话|开户行|账号|合\s*计|小写|大写', it['text']):
            continue
        dx = it['x'] - anchor['x']
        dy = it['y'] - anchor['y']
        if dy < -25 or dy > 40:  # 只看同行或略下方，避免匹配到上方行
            continue
        if dx < -10:  # 只看右侧
            continue
        d = abs(dx) + abs(dy) * 1.2
        if d < best_dist and len(it['text']) >= 2:
            best_dist = d
            best = it['text']
    return best


def _find_field_after_keyword(text, patterns):
    for p in patterns:
        m = re.search(p, text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ''


def _clean_name(name):
    name = re.sub(r'^\s*称?\s*[：:]\s*', '', name)  # 去掉拆块残留的"称："/冒号前缀
    name = re.sub(r'纳税人识别号.*', '', name)
    name = re.sub(r'识别号.*', '', name)
    name = name.strip()
    if name:
        name = re.split(r'\s+', name)[0]  # 名称不含空格，截断行内混入的备注/订单号等
    name = re.sub(r'[：:\s]+$', '', name)
    return name.strip()


def _extract_amounts(full_text, ocr_items, result):
    """提取金额、税额、价税合计：先正则匹配，再坐标定位兜底。"""

    # ---- 价税合计 (total_amount) ----
    for pattern in [
        r'[（(]小写[)）]\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'价税合计.*?[¥￥]\s*([\d,]+\.\d{2})',
        r'价税合计[^\n]{0,20}?([\d,]+\.\d{2})',
        r'([\d,]+\.\d{2})\s*价税合计',
        r'含\s*税\s*合\s*计[^\n]{0,20}?([\d,]+\.\d{2})',
        r'小写[)）]?\s*[¥￥]?\s*([\d,]+\.\d{2})',
    ]:
        m = re.search(pattern, full_text, re.DOTALL)
        if m:
            result['total_amount'] = m.group(1).replace(',', '')
            break

    # ---- 合计行双数字：金额 + 税额 ----
    dual = re.search(
        r'(?<!税)合\s*计\s*[¥￥]?\s*([\d,]+\.\d{2})\s+[¥￥]?\s*([\d,]+\.\d{2})',
        full_text)
    if dual:
        val1 = dual.group(1).replace(',', '')
        val2 = dual.group(2).replace(',', '')
        if val1 != result.get('total_amount'):
            if not result.get('amount'):
                result['amount'] = val1
            if not result.get('tax_amount'):
                result['tax_amount'] = val2

    # ---- 合计金额 (amount) 单数字兜底 ----
    if not result['amount']:
        for pattern in [
            r'(?<!税)合\s*计.*?[¥￥]\s*([\d,]+\.\d{2})',
            r'(?<!税)合\s*计[^\n]{0,30}?([\d,]+\.\d{2})',
            r'合\s*计\s*金\s*额[^\n]{0,20}?([\d,]+\.\d{2})',
            r'金\s*额\s*合\s*计[^\n]{0,20}?([\d,]+\.\d{2})',
        ]:
            m = re.search(pattern, full_text)
            if m:
                val = m.group(1).replace(',', '')
                if val != result.get('total_amount'):
                    result['amount'] = val
                    break

    # ---- 税额 (tax_amount) ----
    if not result['tax_amount']:
        for pattern in [
            r'税\s*额.*?[¥￥]\s*([\d,]+\.\d{2})',
            r'(?<!价)税\s*额[^\n]{0,30}?([\d,]+\.\d{2})',
            r'合\s*计\s*税\s*额[^\n]{0,20}?([\d,]+\.\d{2})',
            r'税\s*额\s*合\s*计[^\n]{0,20}?([\d,]+\.\d{2})',
        ]:
            m = re.search(pattern, full_text)
            if m:
                result['tax_amount'] = m.group(1).replace(',', '')
                break

    # ---- 坐标定位兜底 ----
    if not result['total_amount'] or not result['amount'] or not result['tax_amount']:
        _extract_amounts_by_position(ocr_items, result)

    # ---- 免税发票：税额为 0，金额即价税合计 ----
    if (not result['amount'] and not result['tax_amount']
            and result['total_amount'] and '免税' in full_text):
        result['amount'] = result['total_amount']
        result['tax_amount'] = '0.00'

    # ---- 差值推算税额 ----
    if not result['tax_amount'] and result['total_amount'] and result['amount']:
        try:
            tax = float(result['total_amount']) - float(result['amount'])
            if tax >= 0:
                result['tax_amount'] = f"{tax:.2f}"
        except ValueError:
            pass


def _extract_amounts_by_position(ocr_items, result):
    """坐标定位兜底：根据关键词与金额 item 的相对位置匹配。"""
    DECIMAL_RE = re.compile(r'[¥￥]?\s*([\d,]+\.\d{2})')

    amount_items = []
    for it in ocr_items:
        text = it['text'].strip().replace(' ', '')
        for m in DECIMAL_RE.finditer(text):
            amount_items.append({
                'item': it,
                'value': m.group(1).replace(',', ''),
            })

    if not amount_items:
        return

    total_kw = None
    subtotal_kw = None
    for it in ocr_items:
        text = re.sub(r'\s', '', it['text'])
        if total_kw is None and ('价税合计' in text or '小写' in text):
            total_kw = it
        if subtotal_kw is None and re.search(r'(?<!价税)合计', text):
            subtotal_kw = it

    ROW_THRESH = 25

    # 价税合计行：同行任意位置的金额（全电发票中金额可能在关键词左侧）
    if not result['total_amount'] and total_kw:
        row = [a for a in amount_items
               if abs(a['item']['y'] - total_kw['y']) < ROW_THRESH]
        if row:
            result['total_amount'] = max(row, key=lambda a: float(a['value']))['value']

    # 合计行：左侧为金额，右侧为税额
    if subtotal_kw and (not result['amount'] or not result['tax_amount']):
        row = [a for a in amount_items
               if abs(a['item']['y'] - subtotal_kw['y']) < ROW_THRESH
               and a['item']['x'] >= subtotal_kw['x']]
        row.sort(key=lambda a: a['item']['x'])
        if len(row) >= 2:
            if not result['amount']:
                result['amount'] = row[0]['value']
            if not result['tax_amount']:
                result['tax_amount'] = row[-1]['value']
        elif len(row) == 1 and not result['amount']:
            result['amount'] = row[0]['value']

    # 数值校验兑底："合计"标签漏识别时，在带货币符号的金额里找 金额+税额=价税合计 的组合
    if result['total_amount'] and not result['amount'] and not result['tax_amount']:
        try:
            total = float(result['total_amount'])
        except ValueError:
            return
        cands = sorted({float(a['value']) for a in amount_items
                        if re.search(r'[¥￥]', a['item']['text'])
                        and 0 < float(a['value']) < total}, reverse=True)
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                if abs(cands[i] + cands[j] - total) < 0.005:
                    result['amount'] = f"{cands[i]:.2f}"
                    result['tax_amount'] = f"{cands[j]:.2f}"
                    return
