import customtkinter as ctk
import pandas as pd
from sqlalchemy import create_engine
import urllib.parse
from tkinter import messagebox

# =================================================================
# CORE BACKEND: Strategic Decision Engine
# =================================================================


        try:
            self.engine = create_engine(self.DB_URL)
        except Exception as e:
            self.engine = None
            print(f"Engine Creation Error: {e}")

    def get_latest_metrics(self):
        """
        Fetch live baseline metrics from the Azadea database.
        Uses 90-day window for stable averages, and pulls real customer count.
        """
        if not self.engine:
            raise ConnectionError("Database engine not initialized.")

        query = """
        SELECT
            COALESCE(SUM(s.Net_Amount), 0)                  AS total_revenue,
            COALESCE(AVG(p.Price_JOD), 0)                   AS avg_price,
            COALESCE(AVG(p.Cost_JOD), 0)                    AS avg_cost,
            COALESCE(AVG(p.Price_JOD - p.Cost_JOD), 0)     AS avg_margin,
            COUNT(DISTINCT s.Transaction_ID)                 AS total_transactions,
            COALESCE(SUM(s.Quantity), 0)                    AS total_units,
            COUNT(DISTINCT s.Customer_ID)                   AS total_customers
        FROM fact_sales s
        JOIN dim_products p ON s.Product_ID = p.Product_ID
        WHERE s.Timestamp >= DATE_SUB(NOW(), INTERVAL 90 DAY)
        """
        row = pd.read_sql(query, self.engine).iloc[0].to_dict()

        # Derive margin percentage for use in risk scoring
        if row['avg_price'] > 0:
            row['margin_pct'] = row['avg_margin'] / row['avg_price']
        else:
            row['margin_pct'] = 0.0

        return row

    def calculate_total_impact(self, p_val, d_val, i_val, w_val, r_val):
        """
        Synchronized Decision Engine.

        Parameters (all in %):
          p_val  — Price Adjustment      (0–40%)
          d_val  — Discount Campaign     (0–60%)
          i_val  — Inventory Expansion   (0–50%)
          w_val  — Workforce Capacity    (0–30%)
          r_val  — Stock Reallocation    (0–100%)

        Elasticity assumptions (fashion retail):
          Price elasticity of demand      : -1.5  (a 10% price hike → ~15% volume drop)
          Discount elasticity of demand   : +1.8  (a 10% discount → ~18% volume lift)
          Inventory availability effect   : +0.3  (reduces lost-sale rate)
          Workforce effect on margin      : +0.08% per 1% capacity (efficiency gains)
          Stock reallocation risk reducer : lowers operational risk score
        """
        m = self.get_latest_metrics()

        base_revenue     = m['total_revenue']
        base_units       = m['total_units']
        base_customers   = m['total_customers']   # ← real value from DB, not hardcoded
        avg_price        = m['avg_price']
        avg_cost         = m['avg_cost']
        margin_pct       = m['margin_pct']

        # ------------------------------------------------------------------
        # 1. Net price after adjustment and discount
        #    Price goes up by p_val%, then discount d_val% is applied on top.
        # ------------------------------------------------------------------
        net_price = avg_price * (1 + p_val / 100) * (1 - d_val / 100)

        # ------------------------------------------------------------------
        # 2. Volume (units) projection
        #    - Price elasticity: -1.5 per 1% price increase
        #    - Discount lift:    +1.8 per 1% discount (net, after price effect)
        #    - Inventory effect: +0.3 per 1% expansion (recovers lost sales)
        #    Capped at ±80% to avoid unrealistic extremes.
        # ------------------------------------------------------------------
        price_effect     = p_val  * -1.5
        discount_effect  = d_val  *  1.8
        inventory_effect = i_val  *  0.3
        volume_delta_pct = (price_effect + discount_effect + inventory_effect) / 100
        volume_delta_pct = max(-0.80, min(0.80, volume_delta_pct))   # cap
        projected_units  = int(base_units * (1 + volume_delta_pct))

        # ------------------------------------------------------------------
        # 3. Customer projection
        #    Driven by discount attractiveness and workforce service quality.
        #    Price increases push customers away; discounts and better staffing
        #    attract new ones.
        # ------------------------------------------------------------------
        customer_delta_pct = (p_val * -0.5 + d_val * 0.7 + w_val * 0.25) / 100
        customer_delta_pct = max(-0.80, min(1.00, customer_delta_pct))
        projected_customers = int(base_customers * (1 + customer_delta_pct))

        # ------------------------------------------------------------------
        # 4. Revenue projection
        #    Projected revenue = net_price × projected_units
        #    Workforce adds a small throughput/conversion uplift (max ~2.4%).
        #    Stock reallocation reduces stock-out losses (max ~1%).
        # ------------------------------------------------------------------
        workforce_uplift    = 1 + (w_val * 0.0008)   # 0.08% per 1% capacity
        reallocation_uplift = 1 + (r_val * 0.0001)   # 0.01% per 1% reallocation
        projected_revenue   = net_price * projected_units * workforce_uplift * reallocation_uplift

        # ------------------------------------------------------------------
        # 5. Profit impact
        #    Baseline profit uses actual margin from DB.
        #    Projected profit = (net_price - cost) × projected_units,
        #    with a small workforce efficiency boost on cost (max 2.4% cost saving).
        # ------------------------------------------------------------------
        cost_efficiency  = 1 - (w_val * 0.0008)        # workforce reduces unit cost slightly
        effective_cost   = avg_cost * cost_efficiency

        baseline_profit  = (avg_price - avg_cost)  * base_units
        projected_profit = (net_price - effective_cost) * projected_units

        # Guard: if margin is squeezed below cost, flag it
        margin_compressed = net_price < effective_cost
        profit_delta = projected_profit - baseline_profit

        # ------------------------------------------------------------------
        # 6. Qualitative metrics
        # ------------------------------------------------------------------
        efficiency = "Optimized" if w_val > 15 else ("Improving" if w_val > 5 else "Baseline")
        traffic    = "High Traffic" if (d_val > 20 or w_val > 15) else "Normal"

        # ------------------------------------------------------------------
        # 7. Risk scoring (0–100 scale)
        #    - High price increase compresses volume → revenue volatility
        #    - High discount eats into margin → profit risk
        #    - Low stock reallocation → supply-chain risk
        #    - Margin compression is a hard risk flag
        # ------------------------------------------------------------------
        price_risk       = p_val  * 0.50   # price hike risk
        discount_risk    = d_val  * 0.35   # margin erosion risk
        supply_risk      = (100 - r_val) * 0.15   # stock-out risk
        margin_risk      = 25 if margin_compressed else 0

        risk_score = price_risk + discount_risk + supply_risk + margin_risk

        if risk_score > 40:
            risk_level = "High"
        elif risk_score > 20:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Revenue change vs baseline (%)
        rev_change = ((projected_revenue - base_revenue) / base_revenue * 100) if base_revenue > 0 else 0

        return {
            "Revenue":          projected_revenue,
            "Profit":           profit_delta,
            "Volume":           projected_units,
            "Customers":        projected_customers,
            "BaseCustomers":    base_customers,
            "Efficiency":       efficiency,
            "Traffic":          traffic,
            "Risk":             risk_level,
            "MarginAlert":      margin_compressed,
            "Revenue_Change":   rev_change,
        }


# =================================================================
# GUI INTERFACE: Executive Simulation Dashboard
# =================================================================
class SimulationApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.simulator = StrategicSimulator()

        self.title("ZARA Intelligence | Strategic Simulation App")
        self.geometry("1400x900")
        ctk.set_appearance_mode("dark")

        # Color Palette
        self.PURPLE     = '#4B0082'
        self.MID_PURPLE = '#9d4edd'
        self.BG_DARK    = '#0a0a0a'
        self.CARD_BG    = '#161616'
        self.TEXT_GRAY  = '#bbbbbb'

        self.configure(fg_color=self.BG_DARK)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ------------------------------------------------------------------
        # Sidebar: Control Panel
        # ------------------------------------------------------------------
        self.sidebar = ctk.CTkFrame(self, width=350, corner_radius=0, fg_color="#111111")
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(
            self.sidebar, text="Decision Matrix",
            font=("Outfit", 26, "bold"), text_color="white"
        ).pack(pady=(40, 30))

        self.sliders = {}
        scenarios = [
            # (label,               min, max, default)
            ("Price Adjustment",     0,  40,   0),   # 0 = no change = true baseline
            ("Discount Campaign",    0,  60,   0),
            ("Inventory Expansion",  0,  50,   0),
            ("Workforce Capacity",   0,  30,   0),
            ("Stock Reallocation",   0, 100,   0),
        ]
        for name, start, end, default in scenarios:
            self.create_slider_group(name, start, end, default)

        self.run_btn = ctk.CTkButton(
            self.sidebar, text="Execute All Scenarios",
            command=self.run_synchronized_sim,
            fg_color=self.PURPLE, hover_color=self.MID_PURPLE,
            height=55, font=("Arial", 18, "bold"), corner_radius=10
        )
        self.run_btn.pack(pady=50, padx=30, fill="x")

        self.status_lbl = ctk.CTkLabel(
            self.sidebar, text="System Ready",
            font=("Arial", 12), text_color="#555"
        )
        self.status_lbl.pack(side="bottom", pady=20)

        # ------------------------------------------------------------------
        # Main View: Impact Grid
        # ------------------------------------------------------------------
        self.main_view = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_view.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)

        ctk.CTkLabel(
            self.main_view, text="Strategic Impact Assessment",
            font=("Outfit", 36, "bold"), text_color="white"
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            self.main_view,
            text="Real-time predictive analytics based on current live data",
            font=("Arial", 14), text_color="#666"
        ).pack(pady=(0, 40))

        self.cards_container = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.cards_container.pack(expand=True, fill="both")
        self.cards_container.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.cards_container.grid_rowconfigure((0, 1), weight=1)

        self.card_revenue    = self.create_metric_card("Revenue Impact",         0, 0)
        self.card_profit     = self.create_metric_card("Net Profit Impact",      0, 1)
        self.card_volume     = self.create_metric_card("Units Sold Impact",      0, 2)
        self.card_customers  = self.create_metric_card("Projected Customers",    0, 3)
        self.card_efficiency = self.create_metric_card("Operational Efficiency", 1, 0)
        self.card_traffic    = self.create_metric_card("Transaction Status",     1, 1)
        self.card_risk       = self.create_metric_card("Strategic Risk Level",   1, 2)
        self.card_margin     = self.create_metric_card("Margin Health",          1, 3)

    # ------------------------------------------------------------------
    # Widget builders
    # ------------------------------------------------------------------
    def create_slider_group(self, name, start, end, default):
        frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        frame.pack(pady=12, padx=25, fill="x")

        lbl_frame = ctk.CTkFrame(frame, fg_color="transparent")
        lbl_frame.pack(fill="x")

        ctk.CTkLabel(
            lbl_frame, text=name,
            font=("Arial", 13), text_color=self.TEXT_GRAY
        ).pack(side="left")

        val_lbl = ctk.CTkLabel(
            lbl_frame, text=f"{default}%",
            font=("Arial", 13, "bold"), text_color=self.MID_PURPLE
        )
        val_lbl.pack(side="right")

        slider = ctk.CTkSlider(
            frame, from_=start, to=end, number_of_steps=end - start,
            button_color=self.MID_PURPLE, progress_color=self.PURPLE,
            command=lambda v, l=val_lbl: l.configure(text=f"{int(v)}%")
        )
        slider.pack(pady=(5, 0), fill="x")
        slider.set(default)
        self.sliders[name] = slider

    def create_metric_card(self, title, row, col):
        card = ctk.CTkFrame(
            self.cards_container, fg_color=self.CARD_BG,
            corner_radius=20, border_width=1, border_color="#222"
        )
        card.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")

        ctk.CTkLabel(
            card, text=title,
            font=("Arial", 14), text_color="#888"
        ).pack(pady=(25, 5))

        val_lbl = ctk.CTkLabel(
            card, text="---",
            font=("Outfit", 30, "bold"), text_color=self.MID_PURPLE
        )
        val_lbl.pack(pady=(5, 10))

        sub_lbl = ctk.CTkLabel(card, text="", font=("Arial", 12), text_color="#444")
        sub_lbl.pack(pady=(0, 20))

        return {"value": val_lbl, "sub": sub_lbl, "frame": card}

    # ------------------------------------------------------------------
    # Simulation runner
    # ------------------------------------------------------------------
    def run_synchronized_sim(self):
        self.status_lbl.configure(
            text="Connecting to Live Database...", text_color=self.MID_PURPLE
        )
        self.update_idletasks()

        try:
            p = self.sliders["Price Adjustment"].get()
            d = self.sliders["Discount Campaign"].get()
            i = self.sliders["Inventory Expansion"].get()
            w = self.sliders["Workforce Capacity"].get()
            r = self.sliders["Stock Reallocation"].get()

            res = self.simulator.calculate_total_impact(p, d, i, w, r)

        except Exception as e:
            self.status_lbl.configure(
                text="Database Connection Error", text_color="#f87171"
            )
            messagebox.showerror(
                "Database Connection Error",
                f"Unable to reach cloud host at 34.28.22.11.\n\nDetails: {e}"
            )
            return

        try:
            rev_val    = round(res['Revenue'], 2)
            profit_val = round(res['Profit'],  2)
            rev_change = round(res['Revenue_Change'], 2)

            # Revenue card
            self.card_revenue["value"].configure(text=f"{rev_val:,.2f} JOD")
            self.card_revenue["sub"].configure(text=f"{rev_change:+.2f}% vs baseline")

            # Profit card
            profit_color = "#4ade80" if profit_val >= 0 else "#f87171"
            profit_border = "#1e3a2f" if profit_val >= 0 else "#3a1e1e"
            self.card_profit["value"].configure(
                text=f"{profit_val:+,.2f} JOD", text_color=profit_color
            )
            self.card_profit["frame"].configure(border_color=profit_border)

            # Volume card
            self.card_volume["value"].configure(text=f"{int(res['Volume']):,} Units")

            # Customers card — color relative to real DB baseline
            cust       = int(res['Customers'])
            base_cust  = int(res['BaseCustomers'])
            cust_color = "#4ade80" if cust >= base_cust else "#f87171"
            self.card_customers["value"].configure(
                text=f"{cust:,} Users", text_color=cust_color
            )
            self.card_customers["sub"].configure(
                text=f"Baseline: {base_cust:,}", text_color="#555"
            )

            # Efficiency
            eff_colors = {"Optimized": "#4ade80", "Improving": "#fbbf24", "Baseline": "#888"}
            self.card_efficiency["value"].configure(
                text=res['Efficiency'],
                text_color=eff_colors.get(res['Efficiency'], self.MID_PURPLE)
            )

            # Traffic
            self.card_traffic["value"].configure(text=res['Traffic'])

            # Risk
            risk        = res['Risk']
            risk_colors = {"Low": "#4ade80", "Medium": "#fbbf24", "High": "#f87171"}
            self.card_risk["value"].configure(
                text=f"{risk} Risk",
                text_color=risk_colors.get(risk, self.MID_PURPLE)
            )

            # Margin Health (new card — alerts when net_price < cost)
            if res['MarginAlert']:
                self.card_margin["value"].configure(
                    text="⚠ Negative", text_color="#f87171"
                )
                self.card_margin["sub"].configure(
                    text="Price below cost", text_color="#f87171"
                )
                self.card_margin["frame"].configure(border_color="#3a1e1e")
            else:
                self.card_margin["value"].configure(
                    text="✓ Healthy", text_color="#4ade80"
                )
                self.card_margin["sub"].configure(text="", text_color="#555")
                self.card_margin["frame"].configure(border_color="#222")

            self.status_lbl.configure(
                text="Simulation Synchronized ✓", text_color="#4ade80"
            )

        except Exception as e:
            self.status_lbl.configure(
                text="Data Formatting Error", text_color="#f87171"
            )
            messagebox.showerror(
                "Data Formatting Error",
                f"Calculated data could not be displayed.\n\nDetails: {e}"
            )


if __name__ == "__main__":
    app = SimulationApp()
    app.after(1000, app.run_synchronized_sim)
    app.mainloop()
