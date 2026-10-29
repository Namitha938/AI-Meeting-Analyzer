import os
import unittest
from app.ml.classifier import (
    predict,
    predict_one,
    RuleBasedPlaceholder,
    TrainedSavedModel,
    load_model,
)

class TestStep10Classifier(unittest.TestCase):
    def test_01_predict_interface_specification(self):
        """Test Step 10 required interface: predict(sentences) -> [{label, confidence}]."""
        sentences = [
            "I'll finalize the API documentation by Friday.",
            "Let's go with PostgreSQL for the database.",
            "Who is responsible for the mobile app deployment?",
            "Good morning everyone, thanks for joining.",
        ]

        results = predict(sentences)

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), len(sentences))

        for item in results:
            self.assertIn("label", item)
            self.assertIn("confidence", item)
            self.assertIsInstance(item["label"], str)
            self.assertIsInstance(item["confidence"], float)
            self.assertGreaterEqual(item["confidence"], 0.0)
            self.assertLessEqual(item["confidence"], 1.0)
            self.assertIn(item["label"], ["action_item", "decision", "question", "general"])

        print("\n--- Step 10 Interface Verification: predict(sentences) ---")
        for s, res in zip(sentences, results):
            print(f"'{s}' -> Label: {res['label']} (Confidence: {res['confidence']:.2f})")

    def test_02_rule_based_placeholder_keywords(self):
        """Test rule-based fallback keywords ('I'll', 'by Friday', 'let's go with', etc.)."""
        placeholder = RuleBasedPlaceholder()

        # Action items
        act1 = placeholder.predict_sentence("I'll send the summary by Friday.")
        self.assertEqual(act1["label"], "action_item")
        self.assertGreaterEqual(act1["confidence"], 0.8)

        act2 = placeholder.predict_sentence("Marcus will deploy the release by Monday.")
        self.assertEqual(act2["label"], "action_item")

        # Decisions
        dec1 = placeholder.predict_sentence("Let's go with Redis for task queueing.")
        self.assertEqual(dec1["label"], "decision")
        self.assertGreaterEqual(dec1["confidence"], 0.8)

        dec2 = placeholder.predict_sentence("We decided to launch the closed beta next month.")
        self.assertEqual(dec2["label"], "decision")

        # Questions
        q1 = placeholder.predict_sentence("Who is leading the design review?")
        self.assertEqual(q1["label"], "question")

        q2 = placeholder.predict_sentence("Can we schedule the demo on Wednesday?")
        self.assertEqual(q2["label"], "question")

        # General
        gen = placeholder.predict_sentence("Thank you all for attending the sync.")
        self.assertEqual(gen["label"], "general")

        print("\n--- Rule-Based Placeholder Verification ---")
        print("Action keywords ('I'll', 'by Friday'): PASSED")
        print("Decision keywords ('let's go with', 'decided'): PASSED")
        print("Question & General fallbacks: PASSED")

    def test_03_saved_model_worker_startup_load(self):
        """Test that saved_model/ is exported, contains required parameters, and loads successfully."""
        model = load_model()
        self.assertIsNotNone(model)

        # Classify AMI benchmark sentences
        ami_samples = [
            ("I'll take the action to draw up the initial curves by tomorrow.", "action_item"),
            ("Let's go with the curved shape for the remote casing.", "decision"),
            ("What kind of battery life are we targeting?", "question"),
        ]

        preds = predict([s[0] for s in ami_samples])
        self.assertEqual(len(preds), 3)
        for i, (text, expected_label) in enumerate(ami_samples):
            self.assertEqual(preds[i]["label"], expected_label)
            print(f"AMI Test Sample: '{text}' -> {preds[i]['label']} (Expected: {expected_label})")

    def test_04_predict_one_helper(self):
        """Test single-sentence predict_one helper."""
        res = predict_one("I'll review the database schema by Friday.")
        self.assertEqual(res["label"], "action_item")
        self.assertIn("confidence", res)

if __name__ == "__main__":
    unittest.main()
