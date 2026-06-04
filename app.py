from flask import Flask, request, jsonify
import pdfplumber
import re

app = Flask(__name__)

# كلمة السر لحماية الـ API
API_SECURITY_KEY = "VectorVibe_Secure_Token_2026"

@app.route('/extract', methods=['POST'])
def extract_blueprint():
    # 1. التحقق من مفتاح الحماية
    if request.headers.get("X-API-KEY") != API_SECURITY_KEY:
        return jsonify({"status": "error", "message": "Unauthorized access!"}), 401

    if 'pdf_file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['pdf_file']
    extracted_data = {"status": "success", "items": []}
    
    try:
        with pdfplumber.open(file.stream) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    # محرك بحث ذكي (Regex) لاستخراج الرمز والمقاسات
                    # يبحث عن أنماط مثل: W1 1.20 x 1.50 أو D2 0.90 * 2.20
                    pattern = re.compile(r'([A-Za-z]+\d+)[\s\-\:]*([\d\.]+)[\s[xX\*]+([\d\.]+)')
                    matches = pattern.findall(text)
                    
                    for match in matches:
                        extracted_data["items"].append({
                            "symbol": match[0].upper(), # الرمز (مثال: W1)
                            "width": float(match[1]),   # العرض
                            "height": float(match[2]),  # الارتفاع
                            "qty": 1
                        })
        
        # فلترة العناصر لإزالة التكرار لو تم قراءة نفس الشباك مرتين
        unique_items = { f"{item['symbol']}_{item['width']}_{item['height']}": item for item in extracted_data["items"] }
        extracted_data["items"] = list(unique_items.values())

        return jsonify(extracted_data), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# مسار بسيط لعمل Ping من UptimeRobot لإبقاء السيرفر مستيقظاً
@app.route('/ping', methods=['GET'])
def ping():
    return "I am awake!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)