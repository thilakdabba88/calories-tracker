import streamlit as st
import requests
import sqlite3
import hashlib
from datetime import datetime
import os



# ================= CONFIG =================
USDA_API_KEY = os.getenv("USDA_API_KEY")
SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
DB_NAME = os.path.join(os.getcwd(), "meal.db")

st.set_page_config(page_title="Universal Macro Calculator", page_icon="🥗")

# ================= DATABASE =================
def get_db():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS meal_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER,
            food_name TEXT,
            quantity REAL,
            protein REAL,
            carbs REAL,
            fat REAL,
            calories REAL
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= SESSION STATE =================
if "user" not in st.session_state:
    st.session_state.user = None

if "meal" not in st.session_state:
    st.session_state.meal = []

if "foods" not in st.session_state:
    st.session_state.foods = []

if "selected_food" not in st.session_state:
    st.session_state.selected_food = None

if "add_qty" not in st.session_state:
    st.session_state.add_qty = 100.0

# ================= AUTH =================
def auth_ui():
    st.title("🔐 Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM users WHERE username=?", (u,))
        row = cur.fetchone()
        conn.close()

        if row and row[1] == hash_password(p):
            st.session_state.user = {"id": row[0], "username": u}
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.divider()
    st.subheader("Register")

    nu = st.text_input("New username")
    np = st.text_input("New password", type="password")

    if st.button("Create account"):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (nu, hash_password(np))
            )
            conn.commit()
            conn.close()
            st.success("Account created. Please login.")
        except sqlite3.IntegrityError:
            st.error("Username already exists")

if not st.session_state.user:
    auth_ui()
    st.stop()

# ================= HEADER =================
st.title("🥗 Universal Food Macro Calculator")
st.caption(f"Logged in as **{st.session_state.user['username']}**")

if st.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ================= SEARCH =================
food_query = st.text_input("Search food", placeholder="apple, biryani, chicken curry")

if st.button("🔍 Search") and food_query.strip():
    r = requests.get(
        SEARCH_URL,
        params={"query": food_query, "pageSize": 5, "api_key": USDA_API_KEY},
        timeout=10
    )
    st.session_state.foods = r.json().get("foods", [])
    st.session_state.selected_food = None

# ================= FOOD SELECTION =================
if st.session_state.foods:
    name = st.selectbox(
        "Select food",
        [f["description"] for f in st.session_state.foods]
    )
    st.session_state.selected_food = next(
        f for f in st.session_state.foods if f["description"] == name
    )

# ================= LIVE MACRO PREVIEW =================
if st.session_state.selected_food:
    food = st.session_state.selected_food

    nutrients = {
        n["nutrientName"]: float(n["value"])
        for n in food.get("foodNutrients", [])
    }

    base_p = nutrients.get("Protein", 0.0)
    base_c = nutrients.get("Carbohydrate, by difference", 0.0)
    base_f = nutrients.get("Total lipid (fat)", 0.0)
    base_cal = nutrients.get("Energy", base_p*4 + base_c*4 + base_f*9)

    st.subheader("Quantity (grams)")
    c1, c2, c3 = st.columns([1, 2, 1])

    if c1.button("➖"):
        st.session_state.add_qty = max(1.0, st.session_state.add_qty - 10.0)

    st.session_state.add_qty = c2.number_input(
        " ",
        min_value=1.0,
        value=float(st.session_state.add_qty),
        step=10.0,
        label_visibility="collapsed"
    )

    if c3.button("➕"):
        st.session_state.add_qty += 10.0

    qty = float(st.session_state.add_qty)

    protein = base_p * qty / 100
    carbs = base_c * qty / 100
    fat = base_f * qty / 100
    calories = base_cal * qty / 100

    st.info(
        f"""
**Live Macro Preview ({qty:.0f} g)**  
🥩 Protein: {protein:.1f} g  
🍞 Carbs: {carbs:.1f} g  
🥑 Fat: {fat:.1f} g  
🔥 Calories: {calories:.0f} kcal
"""
    )

    if st.button("➕ Add to Meal"):
        st.session_state.meal.append({
            "name": food["description"],
            "quantity": qty,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "calories": calories
        })
        st.session_state.add_qty = 100.0
        st.rerun()

# ================= CURRENT MEAL =================
st.divider()
st.subheader("🍽️ Current Meal")

total_p = total_c = total_f = total_cal = 0.0

for i, item in enumerate(st.session_state.meal):
    c1, c2, c3 = st.columns([5, 3, 1])

    with c1:
        st.write(f"**{item['name']}**")
        st.caption(
            f"{item['quantity']:.0f} g | "
            f"P {item['protein']:.1f}g | "
            f"C {item['carbs']:.1f}g | "
            f"F {item['fat']:.1f}g | "
            f"Cal {item['calories']:.1f}g"
        )

    with c2:
        new_qty = st.number_input(
            "Qty",
            min_value=1.0,
            value=float(item["quantity"]),
            step=10.0,
            key=f"edit_{i}"
        )

        if new_qty != item["quantity"]:
            factor = new_qty / item["quantity"]
            item["quantity"] = new_qty
            item["protein"] *= factor
            item["carbs"] *= factor
            item["fat"] *= factor
            item["calories"] *= factor
            st.rerun()

    with c3:
        if st.button("❌", key=f"del_{i}"):
            st.session_state.meal.pop(i)
            st.rerun()

    total_p += item["protein"]
    total_c += item["carbs"]
    total_f += item["fat"]
    total_cal += item["calories"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Protein (g)", f"{total_p:.1f}")
c2.metric("Carbs (g)", f"{total_c:.1f}")
c3.metric("Fat (g)", f"{total_f:.1f}")
c4.metric("Calories", f"{total_cal:.0f} kcal")

# ================= SAVE / LOAD =================
st.divider()
st.subheader("💾 Save / Load Meals")

meal_name = st.text_input(
    "Meal name",
    value=f"Meal {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("💾 Save Meal") and st.session_state.meal:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO meals (user_id, name, created_at) VALUES (?, ?, ?)",
            (st.session_state.user["id"], meal_name, datetime.now().isoformat())
        )
        meal_id = cur.lastrowid

        for item in st.session_state.meal:
            cur.execute("""
                INSERT INTO meal_items
                (meal_id, food_name, quantity, protein, carbs, fat, calories)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                meal_id,
                item["name"],
                item["quantity"],
                item["protein"],
                item["carbs"],
                item["fat"],
                item["calories"]
            ))

        conn.commit()
        conn.close()
        st.success("Meal saved")

with c2:
    conn = get_db()
    meals = conn.execute(
        "SELECT id, name FROM meals WHERE user_id=? ORDER BY id DESC",
        (st.session_state.user["id"],)
    ).fetchall()
    conn.close()

    if meals:
        sel = st.selectbox("Load saved meal", meals, format_func=lambda x: x[1])

        if st.button("📂 Load Meal"):
            conn = get_db()
            rows = conn.execute("""
                SELECT food_name, quantity, protein, carbs, fat, calories
                FROM meal_items WHERE meal_id=?
            """, (sel[0],)).fetchall()
            conn.close()

            st.session_state.meal = [
                {
                    "name": r[0],
                    "quantity": r[1],
                    "protein": r[2],
                    "carbs": r[3],
                    "fat": r[4],
                    "calories": r[5]
                }
                for r in rows
            ]
            st.rerun()

with c3:
    if st.button("🧹 Clear Meal"):
        st.session_state.meal = []
        st.rerun()
