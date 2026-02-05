import math
print("🔥 LOADED priority_engine FROM:", __file__)

# ---------------- CATEGORY WEIGHTS ----------------
CATEGORY_WEIGHT = {
    "medicine": 1.0,
    "blood": 1.0,
    "security": 0.87,
    "infrastructure": 0.6,
    "general": 0.5
}

# ---------------- DISTANCE CALCULATION ----------------
def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula to calculate distance in km"""
    R = 6371  # km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = round(R * c, 2)
    return distance

# ---------------- RISK SCORING ----------------
# Dynamic, feedback-ready
WEIGHTS = {
    "urgency": 0.45,
    "impact": 0.45,
    "category": 0.3,
    "distance": 0.1
}

def calculate_risk(urgency, impact, category, distance, people=1, vulnerability="normal", available_resources=1.0, feedback_multiplier=1.0):
    urgency = max(1, min(10, urgency))
    impact = max(1, min(10, impact))
    people_score = min(7, people / 2)
    vulnerability_score = 3 if vulnerability.lower() in ["child","elderly","disabled"] else 0
    combined_impact = min(10, impact + people_score + vulnerability_score)
    distance_score = max(0, 5 - distance/20)  # decay 1 per 20km
    category_score = CATEGORY_WEIGHT.get(category.lower(),0.5) * 5
    raw_score = (
        WEIGHTS["urgency"] * urgency +
        WEIGHTS["impact"] * combined_impact +
        WEIGHTS["category"] * category_score +
        WEIGHTS["distance"] * distance_score
    )
    adjusted_score = min(10, raw_score * available_resources * feedback_multiplier)
    return round(adjusted_score, 2)

# ---------------- PRIORITY CLASSIFICATION ----------------
def classify_request(risk_score):
    if risk_score >= 6.45:
        return "HIGH", "System Auto-Prioritized"
    elif risk_score >= 4:
        return "MEDIUM", "Human-in-the-Loop Required"
    else:
        return "LOW", "Routed to Legacy FIFO System"