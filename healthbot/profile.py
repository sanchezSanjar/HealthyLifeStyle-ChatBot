"""Health profile: BMI, daily calorie, water and protein targets.

Formulas:
- BMI = weight (kg) / height (m)^2, WHO adult categories.
- Resting energy (BMR), Mifflin-St Jeor: 10*kg + 6.25*cm - 5*age + 5 (male) / - 161 (female).
- Daily energy (TDEE) = BMR * activity factor; goal adjusts it (-500 kcal lose, +300 kcal gain).
- Water about 35 ml per kg (+0.5 L when active); protein 1.2-1.6 g per kg.
These are general estimates for healthy adults, not medical advice.
"""
import json
from dataclasses import asdict, dataclass

from .config import PROFILE_FILE

ACTIVITY_FACTORS = {
    "sedentary": 1.2,     # little or no exercise
    "light": 1.375,       # 1-3 days a week
    "moderate": 1.55,     # 3-5 days a week
    "active": 1.725,      # 6-7 days a week
    "very_active": 1.9,   # hard training or physical job
}
GOAL_ADJUST = {"lose": -500, "maintain": 0, "gain": 300}
MIN_CALORIES = {"female": 1200, "male": 1500}


@dataclass
class Profile:
    name: str = ""
    age: int = 25
    sex: str = "male"
    height_cm: float = 170.0
    weight_kg: float = 70.0
    activity: str = "light"
    goal: str = "maintain"

    def validate(self):
        problems = []
        if not 14 <= self.age <= 100:
            problems.append("Age should be between 14 and 100.")
        if not 120 <= self.height_cm <= 230:
            problems.append("Height should be between 120 and 230 cm.")
        if not 30 <= self.weight_kg <= 250:
            problems.append("Weight should be between 30 and 250 kg.")
        if self.sex not in MIN_CALORIES:
            problems.append("Sex must be male or female.")
        if self.activity not in ACTIVITY_FACTORS:
            problems.append("Unknown activity level.")
        if self.goal not in GOAL_ADJUST:
            problems.append("Goal must be lose, maintain or gain.")
        return problems

    @property
    def bmi(self):
        return self.weight_kg / (self.height_cm / 100) ** 2

    @property
    def bmi_category(self):
        if self.bmi < 18.5:
            return "Underweight"
        if self.bmi < 25:
            return "Healthy weight"
        if self.bmi < 30:
            return "Overweight"
        return "Obesity"

    @property
    def bmr(self):
        base = 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age
        return base + (5 if self.sex == "male" else -161)

    @property
    def tdee(self):
        return self.bmr * ACTIVITY_FACTORS[self.activity]

    @property
    def calorie_target(self):
        return max(MIN_CALORIES[self.sex], round(self.tdee + GOAL_ADJUST[self.goal]))

    @property
    def water_litres(self):
        extra = 0.5 if self.activity in ("active", "very_active") else 0.0
        return round(self.weight_kg * 0.035 + extra, 1)

    @property
    def protein_range_g(self):
        return round(self.weight_kg * 1.2), round(self.weight_kg * 1.6)

    def summary(self):
        low, high = self.protein_range_g
        return {
            "BMI": f"{self.bmi:.1f}",
            "Category": self.bmi_category,
            "Calories": f"{self.calorie_target:,} kcal/day",
            "Water": f"{self.water_litres} L/day",
            "Protein": f"{low}-{high} g/day",
        }

    def note_for_model(self):
        """Short description added to the system prompt so answers fit the user."""
        goal = {"lose": "lose weight", "maintain": "keep a healthy weight", "gain": "gain weight"}[self.goal]
        return (
            f"User profile: {self.age}-year-old {self.sex}, {self.height_cm:.0f} cm, {self.weight_kg:.0f} kg, "
            f"BMI {self.bmi:.1f} ({self.bmi_category.lower()}), activity {self.activity.replace('_', ' ')}, "
            f"goal: {goal}. Daily targets: about {self.calorie_target} kcal, "
            f"{self.water_litres} L water, {self.protein_range_g[0]}-{self.protein_range_g[1]} g protein."
        )


def load_profile():
    try:
        data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        profile = Profile(**{k: v for k, v in data.items() if k in Profile.__dataclass_fields__})
        return None if profile.validate() else profile
    except (OSError, ValueError, TypeError):
        return None


def save_profile(profile):
    PROFILE_FILE.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")
