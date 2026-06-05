from flask import Flask, request, jsonify
import pdfplumber
import re

app = Flask(__name__)
API_SECURITY_KEY = "VectorVibe_Secure_Token_2026"

def extract_items_from_pdf(file_stream):
    """
    محرك الاستخراج الذكي — 3 محركات متوازية:
    1. جداول BOQ (رموز XX-00 مع كميات)
    2. أبواب وشبابيك (W1, D2 مع أبعاد)
    3. نص حر (مساحات مذكورة في النص)
    """
    raw_items = []

    with pdfplumber.open(file_stream) as pdf:
        full_text = ""

        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + " "

            tables = page.extract_tables()
            for table in tables:

                # =========================================================
                # المحرك 1: جداول الكميات (BOQ) — رموز مثل PT-02, FT-01
                # يبحث في كل خانة عن رمز XX-00 ويستخرج الكمية من نفس السطر
                # =========================================================
                for row in table:
                    if not row:
                        continue
                    row_clean = [str(c).strip() if c else '' for c in row]

                    # البحث عن رمز الصنف في أي خانة في السطر
                    symbol = None
                    for cell in row_clean:
                        m = re.search(r'\b([A-Z]{1,5}-\d+)\b', cell)
                        if m:
                            symbol = m.group(1)
                            break

                    if not symbol:
                        continue

                    # الكمية: أول رقم موجب في الخانات الأولى
                    qty_val = None
                    for cell in row_clean[:4]:
                        clean = re.sub(r'[^\d\.]', '', cell.replace(',', ''))
                        try:
                            v = float(clean)
                            if v > 0:
                                qty_val = v
                                break
                        except:
                            pass

                    if not qty_val:
                        continue

                    # الوحدة
                    unit_val = 'متر مربع'
                    for cell in row_clean:
                        if re.search(r'متر\s*طولي|م\.ط', cell):
                            unit_val = 'متر طولي'
                            break
                        elif re.search(r'حبة|قطعة|عدد', cell):
                            unit_val = 'حبة'
                            break

                    raw_items.append({
                        "sector": "contracting_decor",
                        "symbol": symbol,
                        "width": qty_val,
                        "height": 1.0,
                        "qty": 1,
                        "area": qty_val,
                        "unit": unit_val
                    })

                # =========================================================
                # المحرك 2: أبواب وشبابيك — رموز W1, D2 مع أبعاد (عرض × ارتفاع)
                # =========================================================
                for row in table:
                    if not row:
                        continue
                    row_text = " ".join([str(c) for c in row if c])
                    m = re.search(
                        r'\b([WDwd][-_]?\d+)\b.*?([\d\.]+)\s*[xX×\*]\s*([\d\.]+).*?\b(\d+)\b',
                        row_text
                    )
                    if m:
                        w = float(m.group(2))
                        h = float(m.group(3))
                        q = int(m.group(4))
                        raw_items.append({
                            "sector": "windows_doors",
                            "symbol": m.group(1).upper(),
                            "width": w,
                            "height": h,
                            "qty": q,
                            "area": round(w * h * q, 4),
                            "unit": "متر مربع"
                        })

        # =========================================================
        # المحرك 3: نص حر — مساحات مذكورة صراحةً بجوار رمز الصنف
        # =========================================================
        full_text = full_text.replace('\n', ' ')
        pattern_free = re.compile(
            r'\b([A-Za-z]{1,5}-\d+)\b[^\d]*([\d,\.]+)\s*(?:متر مربع|م\s*²|m2|M2)'
        )
        for m in pattern_free.findall(full_text):
            try:
                area = float(m[1].replace(',', ''))
                if area > 0:
                    raw_items.append({
                        "sector": "contracting_decor",
                        "symbol": m[0].upper(),
                        "width": area,
                        "height": 1.0,
                        "qty": 1,
                        "area": area,
                        "unit": "متر مربع"
                    })
            except:
                pass

    # =========================================================
    # الفلترة الذكية: منع التكرار (أعلى كمية تكسب)
    # =========================================================
    unique = {}
    for item in raw_items:
        key = f"{item['symbol']}_{item['area']}"
        if key not in unique:
            unique[key] = item
        else:
            if item.get('qty', 1) > unique[key].get('qty', 1):
                unique[key] = item

    return list(unique.values())


@app.route('/extract', methods=['POST'])
def extract_blueprint():
    if request.headers.get("X-API-KEY") != API_SECURITY_KEY:
        return jsonify({"status": "error", "message": "Unauthorized access!"}), 401

    if 'pdf_file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    file = request.files['pdf_file']

    try:
        items = extract_items_from_pdf(file.stream)

        # حساب الإجماليات
        total_area = 0.0
        total_perimeter = 0.0

        for item in items:
            area = item.get("area", 0.0)
            q    = item.get("qty", 1)
            w    = item.get("width", 0.0)
            h    = item.get("height", 0.0)

            if item["sector"] == "contracting_decor":
                total_area += area * q
            else:
                total_area += area

            # محيط: 3 جهات للباب، 4 للشباك
            sym = item.get("symbol", "")
            if item["sector"] == "windows_doors":
                if sym.startswith("D"):
                    total_perimeter += ((h * 2) + w) * q
                else:
                    total_perimeter += ((w + h) * 2) * q

        return jsonify({
            "status": "success",
            "total_area": round(total_area, 4),
            "total_perimeter": round(total_perimeter, 4),
            "items": items
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/ping', methods=['GET'])
def ping():
    return "I am awake!", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
