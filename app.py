from flask import Flask, request, jsonify
import pdfplumber
import re

app = Flask(__name__)
API_SECURITY_KEY = "VectorVibe_Secure_Token_2026"

@app.route('/extract', methods=['POST'])
def extract_blueprint():
    if request.headers.get("X-API-KEY") != API_SECURITY_KEY:
        return jsonify({"status": "error", "message": "Unauthorized access!"}), 401

    if 'pdf_file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['pdf_file']
    extracted_data = {"status": "success", "items": []}
    
    try:
        with pdfplumber.open(file.stream) as pdf:
            full_text = ""
            
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + " "
                
                # ====================================================
                # المحرك المتقدم 1: قراءة جداول الكميات (الأبواب والشبابيك)
                # ====================================================
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        # تنظيف الخانات وتحويلها لنصوص واضحة
                        row_text = " ".join([str(cell) for cell in row if cell])
                        
                        # البحث عن رموز النوافذ والأبواب القياسية (مثل W1, D2, W-01) مع المقاسات والكميات
                        match = re.search(r'\b([WDwd][-_\d]|\b[WDwd]\d+)\b.*?([\d\.]+)\s*[xX\*]\s*([\d\.]+).*?\b(\d+)\b', row_text)
                        if match:
                            extracted_data["items"].append({
                                "sector": "windows_doors",
                                "symbol": match.group(1).upper(),
                                "width": float(match.group(2)),
                                "height": float(match.group(3)),
                                "qty": int(match.group(4)),
                                "area": float(match.group(2)) * float(match.group(3)) * int(match.group(4))
                            })

            # تنظيف النص الشامل للمبنى للبحث عن مساحات التشطيبات والمقاولات
            full_text = full_text.replace('\n', ' ')

            # ====================================================
            # المحرك المتقدم 2: محرك المقاولات العامة والديكور
            # يبحث عن أكواد التشطيبات ومساحاتها بالمتر المربع
            # ====================================================
            general_pattern = re.compile(r'([A-Za-z]{2,}\-\d+).*?(?:متر مربع|m2|M2)\s*([\d,\.]+)')
            gen_matches = general_pattern.findall(full_text)
            
            for match in gen_matches:
                symbol = match[0].upper()
                area = float(match[1].replace(',', '').strip())
                
                extracted_data["items"].append({
                    "sector": "contracting_decor",
                    "symbol": symbol,
                    "width": 0.0,
                    "height": 0.0,
                    "qty": 1,
                    "area": area  # إرسال المساحة الصافية مباشرة للـ PHP
                })

        # ====================================================
        # الفلترة الذكية ومنع التكرار التكنيكي
        # ====================================================
        unique_items = {}
        for item in extracted_data["items"]:
            # إنشاء مفتاح فريد يعتمد على الرمز والمقاس والمساحة لضمان عدم التكرار
            unique_key = f"{item['symbol']}_{item['width']}_{item['height']}_{item['area']}"
            if unique_key not in unique_items:
                unique_items[unique_key] = item
            else:
                # إذا تكرر العنصر في صفحة أخرى، نحدث الكمية الأكبر لحصر إجمالي دقيق
                if item['qty'] > unique_items[unique_key]['qty']:
                    unique_items[unique_key]['qty'] = item['qty']

        extracted_data["items"] = list(unique_items.values())
        return jsonify(extracted_data), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/ping', methods=['GET'])
def ping():
    return "I am awake!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
