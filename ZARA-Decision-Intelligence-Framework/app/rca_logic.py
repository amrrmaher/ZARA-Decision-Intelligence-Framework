import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import tkinter as tk
from datetime import datetime, timedelta
import logging

import os
import logging

# الحصول على مسار المجلد الحالي الذي يوجد فيه الملف
current_dir = os.path.dirname(os.path.abspath(__file__))
log_path = os.path.join(current_dir, 'zara_rca_monitor.log')

# إعداد الـ Logging مع تحديد المسار الكامل
logging.basicConfig(
    filename=log_path, 
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True # هذه تضمن إعادة ضبط الإعدادات وتشغيل الملف فوراً
)

logging.info("System Initialized - Zara RCA Shield")

# Database Connection
engine = create_engine("mysql+pymysql://root:Amr%402004@34.28.22.11:3306/azadea")

def fetch_data():
    # Task 1: Dynamic Date Management
    today_date = datetime.now()
    yesterday_date = today_date - timedelta(days=1)
    
    today_str = today_date.strftime('%Y-%m-%d')
    yesterday_str = yesterday_date.strftime('%Y-%m-%d')
    
    logging.info("Starting Daily RCA Monitor")
    anomalies = []
    
        # PHASE 1: Anomaly Trigger (Profit Drop)
    query_daily = f"""
    SELECT DATE(Timestamp) as day, SUM(Net_Amount) as total_profit
    FROM fact_sales
    WHERE Timestamp >= DATE_SUB('{today_str}', INTERVAL 45 DAY)
      AND Timestamp < '{today_str}'
    GROUP BY 1
    ORDER BY 1;
    """

    try:
        with engine.connect() as conn:
            logging.info("Database connected successfully.")
            df_daily = pd.read_sql(query_daily, conn)
    except Exception as e:
        err_msg = f"Database Connection Error: {e}"
        logging.error(err_msg)
        return None, err_msg

    df_daily['day_str'] = df_daily['day'].astype(str)
    df_daily['day'] = pd.to_datetime(df_daily['day'])
    df_daily['weekday'] = df_daily['day'].dt.weekday

    df_yesterday = df_daily[df_daily['day_str'] == yesterday_str]
    actual_profit = 0

    if not df_yesterday.empty:
        actual_profit = float(df_yesterday.iloc[0]['total_profit'])
        yesterday_weekday = df_yesterday.iloc[0]['weekday']

        df_history = df_daily[
            (df_daily['weekday'] == yesterday_weekday) &
            (df_daily['day_str'] < yesterday_str)
        ].tail(5)

        if not df_history.empty:
            sma_sameday = float(df_history['total_profit'].mean())
            sigma = float(df_history['total_profit'].std(ddof=0))
            if pd.isna(sigma):
                sigma = 0.0

            threshold = sma_sameday - (2 * sigma)
            drop_pct = (sma_sameday - actual_profit) / sma_sameday if sma_sameday > 0 else 0

            is_anomaly = (drop_pct > 0.35) or (actual_profit < threshold)

            logging.info(f"Calculated SMA_5Week: ${sma_sameday:,.2f}")
            logging.info(f"Threshold: ${threshold:,.2f}")
            logging.info(f"Yesterday's Actual Profit: ${actual_profit:,.2f}")

            if is_anomaly:
                logging.warning("Profit Anomaly Detected - Starting Root Cause Analysis")

                history_dates_str = "', '".join(df_history['day_str'].astype(str).tolist())

                # =========================
                # STEP 1: WORST BRANCH
                # =========================
                query_branch = f"""
                SELECT 
                    fs.Branch_ID,
                    db.Branch_Name,
                    SUM(CASE WHEN DATE(fs.Timestamp) IN ('{history_dates_str}') THEN fs.Net_Amount ELSE 0 END) / {len(df_history)} as avg_sameday,
                    SUM(CASE WHEN DATE(fs.Timestamp) = '{yesterday_str}' THEN fs.Net_Amount ELSE 0 END) as yesterday_profit
                FROM fact_sales fs
                JOIN dim_branches db ON fs.Branch_ID = db.Branch_ID
                WHERE DATE(fs.Timestamp) IN ('{history_dates_str}', '{yesterday_str}')
                GROUP BY fs.Branch_ID, db.Branch_Name
                HAVING avg_sameday > 0
                """

                with engine.connect() as conn:
                    df_branch = pd.read_sql(query_branch, conn)

                df_branch['drop_pct'] = (df_branch['avg_sameday'] - df_branch['yesterday_profit']) / df_branch['avg_sameday']
                worst_branch = df_branch.loc[df_branch['drop_pct'].idxmax()]

                affected_branch_id = int(worst_branch['Branch_ID'])
                affected_branch_name = worst_branch['Branch_Name']
                branch_drop = float(worst_branch['drop_pct'])

                # =========================
                # STEP 2: SECTION (Worst Section)
                # =========================
                query_section = f"""
                SELECT 
                    ds.Section_Name,
                    SUM(CASE WHEN DATE(fs.Timestamp) IN ('{history_dates_str}') THEN fs.Net_Amount ELSE 0 END) / {len(df_history)} as avg_profit,
                    SUM(CASE WHEN DATE(fs.Timestamp) = '{yesterday_str}' THEN fs.Net_Amount ELSE 0 END) as yesterday_profit
                FROM fact_sales fs
                JOIN dim_products dp ON fs.Product_ID = dp.Product_ID
                JOIN dim_sections ds ON dp.Section_ID = ds.Section_ID
                WHERE fs.Branch_ID = {affected_branch_id}
                  AND DATE(fs.Timestamp) IN ('{history_dates_str}', '{yesterday_str}')
                GROUP BY ds.Section_Name
                HAVING avg_profit > 0
                """

                with engine.connect() as conn:
                    df_section = pd.read_sql(query_section, conn)

                df_section['drop_pct'] = (df_section['avg_profit'] - df_section['yesterday_profit']) / df_section['avg_profit']
                worst_section = df_section.loc[df_section['drop_pct'].idxmax()]

                affected_section_name = worst_section['Section_Name']
                section_drop = float(worst_section['drop_pct'])

                # =========================
                # STEP 3: FLOOR STOCK CHECK (NEW)
                # =========================
                query_stock = f"""
                SELECT AVG(ci.Floor_Qty) as avg_floor
                FROM central_inventory ci
                JOIN dim_products dp ON ci.Product_id = dp.Product_ID
                JOIN dim_sections ds ON dp.Section_ID = ds.Section_ID
                WHERE ci.Branch_ID = {affected_branch_id}
                  AND ds.Section_Name = '{affected_section_name}'
                """

                with engine.connect() as conn:
                    df_stock = pd.read_sql(query_stock, conn)

                avg_floor = df_stock['avg_floor'].iloc[0] if not df_stock.empty else 99
                stock_issue = avg_floor < 4

                # =========================
                # STEP 4: DISCOUNTS IMPACT (NEW)
                # =========================
                query_discount = f"""
                SELECT 
                    SUM(COALESCE(fs.Discount_Amount,0)) as total_discount,
                    SUM(fs.Net_Amount) as total_sales
                FROM fact_sales fs
                WHERE fs.Branch_ID = {affected_branch_id}
                  AND DATE(fs.Timestamp) IN ('{history_dates_str}', '{yesterday_str}')
                """

                with engine.connect() as conn:
                    df_disc = pd.read_sql(query_discount, conn)

                total_discount = float(df_disc['total_discount'].iloc[0] or 0)
                total_sales = float(df_disc['total_sales'].iloc[0] or 1)

                discount_ratio = total_discount / total_sales if total_sales > 0 else 0
                discount_issue = discount_ratio > 0.20   # threshold قابل للتعديل

                # =========================
                # STEP 5: STAFFING CHECK (EXISTING LOGIC)
                # =========================
                query_emp = f"""
                SELECT DATE(Timestamp) as day, COUNT(DISTINCT Employee_ID) as active_employees
                FROM fact_sales
                WHERE Branch_ID = {affected_branch_id}
                  AND DATE(Timestamp) IN ('{history_dates_str}', '{yesterday_str}')
                GROUP BY DATE(Timestamp)
                """

                with engine.connect() as conn:
                    df_emp = pd.read_sql(query_emp, conn)

                yesterday_emp = df_emp[df_emp['day'].astype(str) == yesterday_str]
                hist_emp = df_emp[df_emp['day'].astype(str) != yesterday_str]

                y_emp_count = int(yesterday_emp.iloc[0]['active_employees']) if not yesterday_emp.empty else 0
                avg_hist_emp = float(hist_emp['active_employees'].mean()) if not hist_emp.empty else 0

                staffing_status = "Understaffed" if y_emp_count < avg_hist_emp else "Adequate"

                # =========================
                # ROOT CAUSE PRIORITY LOGIC
                # =========================

                if stock_issue:
                    primary_reason = "Low Floor Stock Availability"
                elif discount_issue:
                    primary_reason = "High Discount Impact"
                elif staffing_status == "Understaffed":
                    primary_reason = "Staffing Shortage"
                else:
                    primary_reason = "Mixed Operational Factors"

                # =========================
                # FINAL ANOMALY APPEND
                # =========================

                anomalies.append({
                    'type': 'profit_drop',
                    'title': '🚨 Phase 1: Profit Drop Alert',
                    'branch_name': affected_branch_name,
                    'section_name': affected_section_name,
                    'drop_pct': section_drop * 100,
                    'staffing_status': staffing_status,
                    'stock_issue': stock_issue,
                    'discount_issue': discount_issue,
                    'primary_reason': primary_reason,
                    'details': f"""
Profit dropped {drop_pct*100:.1f}%.
Branch: {affected_branch_name}
Section: {affected_section_name}
Primary Reason: {primary_reason}
"""
                })

    # PHASE 2: Section Performance Degradation (15-day trend)
    logging.info("Starting Phase 2: Section Performance Analysis (15-day trend)")
    fifteen_days_ago = (yesterday_date - timedelta(days=15)).strftime('%Y-%m-%d')
    
    query_phase2 = f"""
    SELECT 
        fs.Branch_ID,
        db.Branch_Name,
        ds.Section_Name,
        DATE(fs.Timestamp) as day,
        SUM(fs.Net_Amount) as section_revenue
    FROM fact_sales fs
    JOIN dim_products dp ON fs.Product_ID = dp.Product_ID
    JOIN dim_sections ds ON dp.Section_ID = ds.Section_ID
    JOIN dim_branches db ON fs.Branch_ID = db.Branch_ID
    WHERE DATE(fs.Timestamp) >= '{fifteen_days_ago}'
      AND DATE(fs.Timestamp) <= '{yesterday_str}'
    GROUP BY fs.Branch_ID, db.Branch_Name, ds.Section_Name, DATE(fs.Timestamp)
    """
    with engine.connect() as conn:
        df_p2 = pd.read_sql(query_phase2, conn)
        
    df_p2['day'] = df_p2['day'].astype(str)
    
    if not df_p2.empty:
        df_branch_total = df_p2.groupby(['Branch_ID', 'Branch_Name', 'day'])['section_revenue'].sum().reset_index()
        df_branch_total.rename(columns={'section_revenue': 'branch_total_revenue'}, inplace=True)
        
        df_contrib = pd.merge(df_p2, df_branch_total, on=['Branch_ID', 'Branch_Name', 'day'])
        df_contrib['contribution'] = (df_contrib['section_revenue'] / df_contrib['branch_total_revenue']) * 100
        
        # Separate yesterday and history
        df_yesterday_contrib = df_contrib[df_contrib['day'] == yesterday_str]
        df_hist_contrib = df_contrib[df_contrib['day'] != yesterday_str]
        
        # Calculate dynamic baseline: Mean and Std Dev
        baseline = df_hist_contrib.groupby(['Branch_ID', 'Branch_Name', 'Section_Name'])['contribution'].agg(['mean', 'std']).reset_index()
        
        monitored_sections = ['Women', 'Men', 'Kids']
        
        for idx, row in df_yesterday_contrib.iterrows():
            section = row['Section_Name']
            if section not in monitored_sections: continue
            
            branch_id = row['Branch_ID']
            branch_name = row['Branch_Name']
            y_contrib = row['contribution']
            
            # Find baseline for this branch and section
            b_row = baseline[(baseline['Branch_ID'] == branch_id) & (baseline['Section_Name'] == section)]
            if b_row.empty: continue
            
            b_mean = float(b_row['mean'].iloc[0])
            b_std = float(b_row['std'].iloc[0])
            if pd.isna(b_std): b_std = 0.0
            
            dynamic_threshold = b_mean - b_std
            
            if y_contrib < dynamic_threshold:
                logging.warning(f"Phase 2 Anomaly: {branch_name} - {section} contribution at {y_contrib:.1f}% (Mean: {b_mean:.1f}%, Threshold: {dynamic_threshold:.1f}%)")
                
                bottleneck = "Product Mix/Assortment Failure"
                diag_details = "Inventory, Staffing, and Traffic appear normal."
                
                # 1. Inventory Check
                q_inv = f"""
                SELECT AVG(ci.Floor_Qty) as avg_floor
                FROM central_inventory ci
                JOIN dim_products dp ON ci.Product_id = dp.Product_ID
                JOIN dim_sections ds ON dp.Section_ID = ds.Section_ID
                WHERE ci.Branch_ID = {branch_id}
                  AND ds.Section_Name = '{section}'
                """
                with engine.connect() as conn:
                    df_inv = pd.read_sql(q_inv, conn)
                avg_floor = df_inv['avg_floor'].iloc[0] if not df_inv.empty and pd.notna(df_inv['avg_floor'].iloc[0]) else 99
                
                if avg_floor < 4:
                    bottleneck = "Low Stock on Floor"
                    diag_details = f"Average Floor Quantity for {section} is {avg_floor:.1f} (Threshold: < 4)."
                else:
                    # 2. Staffing Check
                    q_staff_trend = f"""
                    SELECT DATE(fs.Timestamp) as day, COUNT(DISTINCT fs.Employee_ID) as staff_count
                    FROM fact_sales fs
                    JOIN dim_products dp ON fs.Product_ID = dp.Product_ID
                    JOIN dim_sections ds ON dp.Section_ID = ds.Section_ID
                    WHERE fs.Branch_ID = {branch_id}
                      AND ds.Section_Name = '{section}'
                      AND DATE(fs.Timestamp) >= '{fifteen_days_ago}'
                      AND DATE(fs.Timestamp) <= '{yesterday_str}'
                    GROUP BY DATE(fs.Timestamp)
                    """
                    with engine.connect() as conn:
                        df_staff = pd.read_sql(q_staff_trend, conn)
                    df_staff['day'] = df_staff['day'].astype(str)
                    
                    y_staff = df_staff[df_staff['day'] == yesterday_str]['staff_count'].sum()
                    hist_staff = df_staff[df_staff['day'] != yesterday_str]['staff_count'].mean()
                    if pd.isna(hist_staff): hist_staff = 0
                    
                    if y_staff < hist_staff:
                        bottleneck = "Staffing Inadequacy"
                        diag_details = f"Active staff for {section} was {y_staff} (15-day average: {hist_staff:.1f})."
                    else:
                        # 3. Traffic Check
                        q_traffic = f"""
                        SELECT DATE(fs.Timestamp) as day, COUNT(DISTINCT fs.Transaction_ID) as traffic_count
                        FROM fact_sales fs
                        JOIN dim_products dp ON fs.Product_ID = dp.Product_ID
                        JOIN dim_sections ds ON dp.Section_ID = ds.Section_ID
                        WHERE fs.Branch_ID = {branch_id}
                          AND ds.Section_Name = '{section}'
                          AND DATE(fs.Timestamp) >= '{fifteen_days_ago}'
                          AND DATE(fs.Timestamp) <= '{yesterday_str}'
                        GROUP BY DATE(fs.Timestamp)
                        """
                        with engine.connect() as conn:
                            df_traffic = pd.read_sql(q_traffic, conn)
                        df_traffic['day'] = df_traffic['day'].astype(str)
                        
                        y_traffic = df_traffic[df_traffic['day'] == yesterday_str]['traffic_count'].sum()
                        hist_traffic = df_traffic[df_traffic['day'] != yesterday_str]['traffic_count'].mean()
                        if pd.isna(hist_traffic): hist_traffic = 0
                        
                        if y_traffic < hist_traffic:
                            bottleneck = "Low Section Traffic"
                            diag_details = f"Section traffic was {y_traffic} transactions (15-day average: {hist_traffic:.1f})."
                
                anomalies.append({
                    'type': 'section_drop',
                    'title': f"📉 Phase 2: Section Performance Alert",
                    'branch_name': branch_name,
                    'section_name': section,
                    'contrib': y_contrib,
                    'expected_contrib': b_mean,
                    'bottleneck': bottleneck,
                    'diag_details': diag_details
                })
                
    result = {
        'yesterday_str': yesterday_str,
        'anomalies': anomalies
    }
    return result, None

class RCADashboard(tk.Tk):
    def __init__(self, data):
        super().__init__()
        self.title("RCA Analysis ZARA - Performance Diagnostics")
        self.geometry("800x400")
        self.configure(bg="#ffffff")
        self.data = data
        self.build_ui()

    def build_ui(self):
        yesterday_str = self.data.get('yesterday_str', 'Unknown Date')
        anomalies = self.data.get('anomalies', [])

        # Main Title
        title_label = tk.Label(
            self,
            text="RCA Analysis ZARA - Performance Diagnostics",
            font=("Arial", 22, "bold"),
            fg="#000000",
            bg="#ffffff"
        )
        title_label.pack(pady=(20, 5))

        # Subtitle indicating Date
        date_label = tk.Label(
            self,
            text=f"Analysis for {yesterday_str} completed.",
            font=("Arial", 14, "italic"),
            fg="#555555",
            bg="#ffffff"
        )
        date_label.pack(pady=(0, 20))

        # Scrollable Frame Implementation
        canvas = tk.Canvas(self, bg="#ffffff", highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#ffffff")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=750)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="top", fill="both", expand=True, padx=40, pady=10)
        scrollbar.pack(side="right", fill="y", in_=canvas)
        
        # Enable mouse scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.bind_all("<MouseWheel>", _on_mousewheel)

        profit_anomalies = [a for a in anomalies if a['type'] == 'profit_drop']
        section_anomalies = [a for a in anomalies if a['type'] == 'section_drop']

        # Point 1: Profit Check
        if not profit_anomalies:
            p1_text = "• 1. Profit Stability Check: No significant drop in profit detected across branches. Performance is consistent with the historical baseline."
            tk.Label(scrollable_frame, text=p1_text, font=("Arial", 14), fg="#2e7d32", bg="#ffffff", anchor="w", justify="left", wraplength=700).pack(fill="x", pady=5)
        else:
            for pa in profit_anomalies:
                p1_text = f"• 1. Profit Drop Alert: Anomaly detected in {pa['branch_name']}."
                tk.Label(scrollable_frame, text=p1_text, font=("Arial", 14, "bold"), fg="#c62828", bg="#ffffff", anchor="w", justify="left", wraplength=700).pack(fill="x", pady=5)
                
                details_frame = tk.Frame(scrollable_frame, bg="#ffffff")
                details_frame.pack(fill="x", padx=(30, 0), pady=2)
                
                tk.Label(details_frame, text=f"Metric: Total profit dropped {pa['drop_pct']:.1f}%.", font=("Arial", 13), fg="#000000", bg="#ffffff", anchor="w", justify="left").pack(fill="x", pady=1)
                tk.Label(details_frame, text=f"Bottleneck Section: {pa['section_name']}.", font=("Arial", 13), fg="#000000", bg="#ffffff", anchor="w", justify="left").pack(fill="x", pady=1)
                tk.Label(details_frame, text=f"Staffing Details: {pa['staffing_status']}.", font=("Arial", 13), fg="#000000", bg="#ffffff", anchor="w", justify="left", wraplength=650).pack(fill="x", pady=1)

        # Point 2: Section Performance
        if section_anomalies:
            for sa in section_anomalies:
                p2_text = f"• 2. Section Performance Alert: Anomaly detected in {sa['branch_name']} | {sa['section_name']}."
                tk.Label(scrollable_frame, text=p2_text, font=("Arial", 14, "bold"), fg="#ef6c00", bg="#ffffff", anchor="w", justify="left", wraplength=700).pack(fill="x", pady=(15, 5))
                
                details_frame = tk.Frame(scrollable_frame, bg="#ffffff")
                details_frame.pack(fill="x", padx=(30, 0), pady=2)
                
                tk.Label(details_frame, text=f"Metric: Contribution: {sa['contrib']:.1f}% (Expected: >= {sa['expected_contrib']}%).", font=("Arial", 13), fg="#000000", bg="#ffffff", anchor="w", justify="left").pack(fill="x", pady=1)
                tk.Label(details_frame, text=f"Bottleneck: {sa['bottleneck']}.", font=("Arial", 13), fg="#000000", bg="#ffffff", anchor="w", justify="left").pack(fill="x", pady=1)
                tk.Label(details_frame, text=f"Evidence: {sa['diag_details']}", font=("Arial", 13), fg="#000000", bg="#ffffff", anchor="w", justify="left", wraplength=650).pack(fill="x", pady=1)
        else:
             p2_text = "• 2. Section Performance Check: No section anomalies detected. Contributions meet expectations."
             tk.Label(scrollable_frame, text=p2_text, font=("Arial", 14), fg="#2e7d32", bg="#ffffff", anchor="w", justify="left", wraplength=700).pack(fill="x", pady=(15, 5))

        # Acknowledge Button - Center at the bottom
        btn_frame = tk.Frame(self, bg="#ffffff")
        btn_frame.pack(side="bottom", fill="x", pady=20)
        
        btn = tk.Button(
            btn_frame,
            text="Acknowledge",
            font=("Arial", 14, "bold"),
            fg="#ffffff",
            bg="#1565c0",
            activebackground="#0d47a1",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            command=self.destroy
        )
        btn.pack(pady=10, ipadx=40, ipady=8)

def main():
    logging.info("--- Starting new execution of RCA Logic script ---")
    data, err = fetch_data()
    if err:
        logging.error(f"Execution aborted due to error: {err}")
        print("Error:", err)
        return
        
    app = RCADashboard(data)
    app.mainloop()
    logging.info("--- Dashboard closed. Execution ended. ---")

if __name__ == "__main__":
    main()
