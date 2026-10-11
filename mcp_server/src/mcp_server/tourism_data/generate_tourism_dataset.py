"""
Indian Tourism Cost Dataset Generator & SQLite Pipeline
-------------------------------------------------------
Author: Senior Data Engineer
Description: Generates a comprehensive, realistic tourism dataset covering
             all 28 Indian States and 8 Union Territories, detailing daily
             estimated tourist costs across Budget, Mid-Range, and Luxury tiers.
Database: SQLite (indian_tourism.db)
"""

import os
import random
import sqlite3
from typing import Dict, List, Tuple

# Comprehensive mapping of All 28 States + 8 Union Territories and key cities/destinations
INDIA_GEOGRAPHY: Dict[str, List[str]] = {
    # 28 States
    "Andhra Pradesh": [
        "Visakhapatnam", "Vijayawada", "Tirupati", "Guntur", "Nellore",
        "Kurnool", "Rajahmundry", "Kakinada", "Kadapa", "Anantapur"
    ],
    "Arunachal Pradesh": [
        "Itanagar", "Tawang", "Ziro", "Pasighat", "Bomdila",
        "Dirang", "Bhalukpong", "Roing", "Tezu", "Mechuka"
    ],
    "Assam": [
        "Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon",
        "Tezpur", "Tinsukia", "Kaziranga", "Majuli", "Sivasagar"
    ],
    "Bihar": [
        "Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Nalanda",
        "Rajgir", "Darbhanga", "Purnia", "Bodh Gaya", "Vaishali"
    ],
    "Chhattisgarh": [
        "Raipur", "Bhilai", "Bilaspur", "Korba", "Jagdalpur",
        "Durg", "Rajnandgaon", "Ambikapur", "Mainpat", "Chitrakote"
    ],
    "Goa": [
        "Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda",
        "Calangute", "Candolim", "Anjuna", "Palolem", "Benaulim"
    ],
    "Gujarat": [
        "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar",
        "Jamnagar", "Gandhinagar", "Bhuj", "Somnath", "Dwarka", "Kevadia"
    ],
    "Haryana": [
        "Gurugram", "Faridabad", "Panipat", "Ambala", "Karnal",
        "Hisar", "Rohtak", "Sonipat", "Panchkula", "Kurukshetra"
    ],
    "Himachal Pradesh": [
        "Shimla", "Manali", "Dharamshala", "Kullu", "Spiti",
        "Kasol", "Dalhousie", "Mandi", "Solan", "Kaza"
    ],
    "Jharkhand": [
        "Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Deoghar",
        "Hazaribagh", "Giridih", "Netarhat", "Jamtara", "Dumka"
    ],
    "Karnataka": [
        "Bengaluru", "Mysuru", "Mangaluru", "Hubballi-Dharwad", "Hampi",
        "Belagavi", "Udupi", "Coorg (Madikeri)", "Chikmagalur", "Gokarna"
    ],
    "Kerala": [
        "Thiruvananthapuram", "Kochi", "Kozhikode", "Munnar", "Alleppey (Alappuzha)",
        "Wayanad", "Varkala", "Thrissur", "Kollam", "Thekkady"
    ],
    "Madhya Pradesh": [
        "Bhopal", "Indore", "Gwalior", "Jabalpur", "Ujjain",
        "Khajuraho", "Pachmarhi", "Orchha", "Bandhavgarh", "Kanha"
    ],
    "Maharashtra": [
        "Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad (Chhatrapati Sambhajinagar)",
        "Lonavala", "Mahabaleshwar", "Alibaug", "Shirdi", "Kolhapur"
    ],
    "Manipur": [
        "Imphal", "Churachandpur", "Ukhrul", "Thoubal", "Moirang",
        "Kakching", "Senapati", "Tamenglong", "Chandel", "Andro"
    ],
    "Meghalaya": [
        "Shillong", "Cherrapunji (Sohra)", "Dawki", "Mawlynnong", "Tura",
        "Jowai", "Nongpoh", "Mawsynram", "Baghmara", "Williamnagar"
    ],
    "Mizoram": [
        "Aizawl", "Lunglei", "Champhai", "Serchhip", "Kolasib",
        "Lawngtlai", "Saitual", "Mamit", "Reiek", "Hmuifang"
    ],
    "Nagaland": [
        "Kohima", "Dimapur", "Mokokchung", "Tuensang", "Wokha",
        "Mon", "Zunheboto", "Phek", "Dzukou Valley", "Khonoma"
    ],
    "Odisha": [
        "Bhubaneswar", "Puri", "Cuttack", "Rourkela", "Konark",
        "Sambalpur", "Balasore", "Berhampur", "Gopalpur", "Koraput"
    ],
    "Punjab": [
        "Amritsar", "Ludhiana", "Jalandhar", "Patiala", "Bathinda",
        "Mohali", "Pathankot", "Hoshiarpur", "Firozpur", "Kapurtala"
    ],
    "Rajasthan": [
        "Jaipur", "Udaipur", "Jodhpur", "Jaisalmer", "Pushkar",
        "Mount Abu", "Bikaner", "Ajmer", "Ranthambore (Sawai Madhopur)", "Chittorgarh"
    ],
    "Sikkim": [
        "Gangtok", "Pelling", "Lachung", "Lachen", "Namchi",
        "Ravangla", "Yuksom", "Geyzing", "Zuluk", "Rinchenpong"
    ],
    "Tamil Nadu": [
        "Chennai", "Coimbatore", "Madurai", "Ooty (Udhagamandalam)", "Kodaikanal",
        "Rameswaram", "Kanyakumari", "Tiruchirappalli", "Mahabalipuram", "Thanjavur"
    ],
    "Telangana": [
        "Hyderabad", "Warangal", "Nizamabad", "Khammam", "Karimnagar",
        "Ramagundam", "Mahbubnagar", "Nalgonda", "Adilabad", "Bhadrachalam"
    ],
    "Tripura": [
        "Agartala", "Udaipur", "Dharmanagar", "Kailashahar", "Ambassa",
        "Belonia", "Khowai", "Teliamura", "Unakoti", "Melaghar"
    ],
    "Uttar Pradesh": [
        "Varanasi", "Agra", "Lucknow", "Prayagraj", "Mathura",
        "Vrindavan", "Ayodhya", "Kanpur", "Noida", "Jhansi"
    ],
    "Uttarakhand": [
        "Dehradun", "Rishikesh", "Haridwar", "Nainital", "Mussoorie",
        "Auli", "Jim Corbett (Ramnagar)", "Kedarnath", "Badrinath", "Almora"
    ],
    "West Bengal": [
        "Kolkata", "Darjeeling", "Siliguri", "Kalimpong", "Digha",
        "Sundarbans", "Shantiniketan", "Murshidabad", "Howrah", "Durgapur"
    ],
    # 8 Union Territories
    "Andaman and Nicobar Islands": ["Port Blair", "Havelock Island (Swaraj Dweep)", "Neil Island (Shaheed Dweep)", "Diglipur"],
    "Chandigarh": ["Chandigarh"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Daman", "Diu", "Silvassa"],
    "Delhi": ["New Delhi", "Old Delhi", "South Delhi", "Connaught Place", "Dwarka"],
    "Jammu and Kashmir": ["Srinagar", "Gulmarg", "Pahalgam", "Jammu", "Sonamarg", "Patnitop"],
    "Ladakh": ["Leh", "Nubra Valley", "Pangong Tso", "Kargil", "Zanskar"],
    "Lakshadweep": ["Kavaratti", "Agatti Island", "Bangaram Island", "Minicoy"],
    "Puducherry": ["Puducherry", "Auroville", "Karaikal", "Mahe"]
}

# Cost multipliers based on tiering (Metros / Premier hill stations vs regular regional destinations)
HIGH_DEMAND_DESTINATIONS = {
    "Mumbai", "Delhi", "New Delhi", "Bengaluru", "Goa", "Panaji", "Calangute",
    "Jaipur", "Udaipur", "Leh", "Gulmarg", "Srinagar", "Havelock Island (Swaraj Dweep)",
    "Agra", "Varanasi", "Kochi", "Munnar", "Darjeeling", "Shimla", "Manali",
    "Rishikesh", "Ooty (Udhagamandalam)", "Hyderabad", "Kolkata", "Chennai"
}

CATEGORY_CONFIG = {
    "Budget": {
        "base_min": 1200,
        "base_max": 2500,
        "high_demand_min": 2000,
        "high_demand_max": 3500,
    },
    "Mid-Range": {
        "base_min": 3500,
        "base_max": 6500,
        "high_demand_min": 5500,
        "high_demand_max": 9500,
    },
    "Luxury": {
        "base_min": 9000,
        "base_max": 18000,
        "high_demand_min": 16000,
        "high_demand_max": 42000,
    }
}


def calculate_cost(city: str, category: str) -> float:
    """Computes realistic daily cost based on category and destination tier."""
    cfg = CATEGORY_CONFIG[category]
    if city in HIGH_DEMAND_DESTINATIONS:
        cost = random.randint(cfg["high_demand_min"], cfg["high_demand_max"])
    else:
        cost = random.randint(cfg["base_min"], cfg["base_max"])
    # Round to nearest 50 for clean, realistic pricing
    return float(round(cost / 50) * 50)


def generate_records() -> List[Tuple[int, str, str, str, float]]:
    """Builds records across all states, cities, and categories."""
    records = []
    record_id = 1
    categories = ["Budget", "Mid-Range", "Luxury"]

    for state, cities in sorted(INDIA_GEOGRAPHY.items()):
        for city in sorted(cities):
            for category in categories:
                cost = calculate_cost(city, category)
                records.append((record_id, state, city, category, cost))
                record_id += 1

    return records


def init_and_populate_db(db_path: str = "indian_tourism.db") -> int:
    """Creates SQLite database, initializes schema, and performs bulk load."""
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Schema definition with proper datatypes and constraints
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tourist_daily_costs (
            id INTEGER PRIMARY KEY,
            state_name TEXT NOT NULL,
            city_name TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('Budget', 'Mid-Range', 'Luxury')),
            daily_estimated_cost REAL NOT NULL
        );
    """)

    # Indexing for optimal query latency on analytics queries
    cursor.execute("CREATE INDEX idx_state_city ON tourist_daily_costs (state_name, city_name);")
    cursor.execute("CREATE INDEX idx_category ON tourist_daily_costs (category);")

    records = generate_records()

    cursor.executemany("""
        INSERT INTO tourist_daily_costs (id, state_name, city_name, category, daily_estimated_cost)
        VALUES (?, ?, ?, ?, ?);
    """, records)

    conn.commit()
    conn.close()
    return len(records)


def verify_dataset(db_path: str = "indian_tourism.db") -> None:
    """Verifies coverage and prints sample statistical summaries."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(DISTINCT state_name) FROM tourist_daily_costs;")
    state_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT city_name) FROM tourist_daily_costs;")
    city_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tourist_daily_costs;")
    total_rows = cursor.fetchone()[0]

    print("\n" + "=" * 50)
    print("DATASET PIPELINE EXECUTION SUMMARY")
    print("=" * 50)
    print(f"Total States & UTs Covered : {state_count}")
    print(f"Total Cities / Towns       : {city_count}")
    print(f"Total Database Records     : {total_rows}")
    print("-" * 50)

    print("\nAverage Daily Cost by Category (INR):")
    cursor.execute("""
        SELECT category, 
               ROUND(AVG(daily_estimated_cost), 2) AS avg_cost, 
               MIN(daily_estimated_cost) AS min_cost, 
               MAX(daily_estimated_cost) AS max_cost
        FROM tourist_daily_costs 
        GROUP BY category 
        ORDER BY avg_cost ASC;
    """)
    for row in cursor.fetchall():
        print(f" - {row[0]:<10}: Avg ₹{row[1]:<8} (Min ₹{row[2]} | Max ₹{row[3]})")

    print("\nSample 5 Records:")
    cursor.execute("SELECT * FROM tourist_daily_costs LIMIT 5;")
    for row in cursor.fetchall():
        print(f"  ID {row[0]:<4} | {row[1]:<20} | {row[2]:<20} | {row[3]:<10} | ₹{row[4]}")
    print("=" * 50 + "\n")

    conn.close()


if __name__ == "__main__":
    db_file = "indian_tourism.db"
    # inserted_count = init_and_populate_db(db_file)
    verify_dataset(db_file)
