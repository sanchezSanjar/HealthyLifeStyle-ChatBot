import unittest

from healthbot.profile import Profile


class ProfileTest(unittest.TestCase):
    def test_bmi_and_category(self):
        p = Profile(height_cm=180, weight_kg=81)
        self.assertAlmostEqual(p.bmi, 25.0, places=2)
        self.assertEqual(p.bmi_category, "Overweight")
        self.assertEqual(Profile(height_cm=170, weight_kg=50).bmi_category, "Underweight")
        self.assertEqual(Profile(height_cm=170, weight_kg=65).bmi_category, "Healthy weight")
        self.assertEqual(Profile(height_cm=160, weight_kg=90).bmi_category, "Obesity")

    def test_mifflin_st_jeor(self):
        # 10*70 + 6.25*175 - 5*30 = 1643.75; +5 male, -161 female
        self.assertAlmostEqual(Profile(age=30, sex="male", height_cm=175, weight_kg=70).bmr, 1648.75)
        self.assertAlmostEqual(Profile(age=30, sex="female", height_cm=175, weight_kg=70).bmr, 1482.75)

    def test_calorie_target_follows_goal(self):
        base = dict(age=30, sex="male", height_cm=175, weight_kg=70, activity="moderate")
        maintain = Profile(goal="maintain", **base).calorie_target
        self.assertEqual(maintain, round(1648.75 * 1.55))
        self.assertEqual(Profile(goal="lose", **base).calorie_target, maintain - 500)
        self.assertEqual(Profile(goal="gain", **base).calorie_target, maintain + 300)

    def test_calorie_floor(self):
        tiny = Profile(age=80, sex="female", height_cm=145, weight_kg=40, activity="sedentary", goal="lose")
        self.assertEqual(tiny.calorie_target, 1200)

    def test_water_and_protein(self):
        p = Profile(weight_kg=80, activity="active")
        self.assertEqual(p.water_litres, 3.3)
        self.assertEqual(p.protein_range_g, (96, 128))

    def test_validation(self):
        self.assertEqual(Profile().validate(), [])
        self.assertEqual(len(Profile(age=5, height_cm=300, weight_kg=10).validate()), 3)

    def test_note_mentions_targets(self):
        note = Profile(goal="lose").note_for_model()
        self.assertIn("goal: lose weight", note)
        self.assertIn("kcal", note)


if __name__ == "__main__":
    unittest.main()
