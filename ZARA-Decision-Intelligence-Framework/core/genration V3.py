import pandas as pd
import time
import random
from datetime import datetime
from sqlalchemy import create_engine, text
import sys

# الاتصال بقاعدة البيانات
engine = create_engine("mysql+mysqlconnector://root:Amr%402004@localhost/azadea")

def run_engine():
    # تحديد السقف المطلوب (رقم عشوائي بين 70 و 82 ألف)
    daily_target = random.randint(70000, 82000)
    print(f"🚀 Engine V15.1 [Immune Peak Time Edition] Active...")
    print(f"🎯 Today's Target: {daily_target} JOD")
    sys.stdout.flush()

    try:
        with engine.connect() as conn:
            products = pd.read_sql("SELECT Product_id FROM dim_products", conn)["Product_id"].tolist()
            employees = pd.read_sql("SELECT Employee_id FROM dim_employees", conn)["Employee_id"].tolist()
            customers = pd.read_sql("SELECT Customer_id FROM dim_customers", conn)["Customer_id"].tolist()
    except Exception as e:
        print(f"❌ Init Error: {e}")
        return

    while True:
        now = datetime.fromtimestamp(time.time())
        current_hour = now.hour
        
        # القيمة الافتراضية لوقت النوم لحماية الكود من الانهيار في حال حدوث خطأ اتصال
        sleep_time = 600 
        
        # 1. التحقق من ساعات العمل (من 11 صباحاً حتى 11 مساءً)
        if current_hour < 11 or current_hour >= 23:
            time.sleep(600)
            continue

        try:
            with engine.connect() as conn:
                # 2. التحقق من إجمالي مبيعات اليوم الحالية
                result = conn.execute(text("SELECT SUM(Gross_Amount) FROM fact_sales WHERE DATE(Timestamp) = CURDATE()"))
                current_revenue = result.scalar() or 0
                
                # 3. الشرط الجوهري: هل وصلنا للهدف؟
                if current_revenue >= daily_target:
                    print(f"✅ Target Reached ({current_revenue:.2f} JOD). Stopping injection for today.")
                    sys.stdout.flush()
                    time.sleep(3600) 
                    continue

                # 4. ضبط ديناميكية التوليد بناءً على الوقت الحالي (هندسة وقت الذروة)
                if 20 <= current_hour <= 22:
                    # 🔥 فترة الذروة المطلوبة (من الساعة 8 مساءً حتى 10:59 ليلاً)
                    invoices_to_inject = random.randint(12, 18) 
                    min_items, max_items = 5, 10
                    min_price, max_price = 70, 180
                    sleep_time = random.uniform(400, 600) 
                    period_name = "🔥 PEAK TIME"
                else:
                    # 🌤️ الفترة الهادئة (باقي اليوم من 11 صباحاً حتى 7:59 مساءً)
                    invoices_to_inject = random.randint(2, 4) 
                    min_items, max_items = 2, 4
                    min_price, max_price = 35, 90
                    sleep_time = random.uniform(800, 1000) 
                    period_name = "🌤️ Off-Peak Hours"

                # 5. بدء عملية الحقن الذكي
                for _ in range(invoices_to_inject):
                    t_id = int(now.strftime('%m%d%H%M%S')) + random.randint(1000, 9999)
                    items_count = random.randint(min_items, max_items)
                    
                    with engine.begin() as trans:
                        for _ in range(items_count):
                            price = round(random.uniform(min_price, max_price), 2)
                            trans.execute(text("""
                                INSERT INTO fact_sales (Branch_ID, Timestamp, Gross_Amount, Net_Amount, Quantity, Product_ID, Employee_ID, Customer_ID, Transaction_id)
                                VALUES (:bid, :ts, :ga, :na, 1, :pid, :eid, :cid, :tid)
                            """), {
                                "bid": random.choice([101, 102]),
                                "ts": now.strftime('%Y-%m-%d %H:%M:%S'),
                                "ga": price, "na": price, 
                                "pid": random.choice(products),
                                "eid": random.choice(employees),
                                "cid": random.choice(customers),
                                "tid": t_id
                            })
                
                print(f"📈 [{period_name}] Rev: {current_revenue:.2f}/{daily_target} | Injected {invoices_to_inject} invoices.")
                sys.stdout.flush()

        except Exception as e:
            print(f"❌ Connection or Runtime Error: {e}")
            print(f"🔄 Retrying in {sleep_time} seconds...")
            sys.stdout.flush()

        # تطبيق وقت الانتظار (الآن أصبح محمياً ومضمون القيمة)
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_engine()