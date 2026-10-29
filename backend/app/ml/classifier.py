import os
import re
import math
import json
import logging
from collections import Counter
from typing import List, Dict, Any

logger = logging.getLogger("meetora.ml.classifier")

class ModelWeightsClassifier:
    def __init__(self, weights_path: str = None):
        if not weights_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            weights_path = os.path.join(base_dir, "saved_model", "model_weights.json")

        self.weights_path = weights_path
        self.is_loaded = False
        self.classes = ["action_item", "decision", "question", "general"]
        self.vocab = {}
        self.idf = {}
        self.weights = []
        self.biases = []
        self._load()

    def _load(self):
        if os.path.exists(self.weights_path):
            try:
                with open(self.weights_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.classes = data.get("classes", self.classes)
                self.vocab = data.get("vocab", {})
                self.idf = data.get("idf", {})
                self.weights = data.get("weights", [])
                self.biases = data.get("biases", [0.0] * len(self.classes))
                self.is_loaded = True
                logger.info(f"Loaded classifier weights from {self.weights_path} ({len(self.vocab)} features, {len(self.classes)} classes)")
            except Exception as e:
                logger.error(f"Failed to load weights: {e}")

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b[a-zA-Z]{2,}\b", text.lower())

    def _transform(self, text: str) -> List[float]:
        words = self._tokenize(text)
        counts = Counter(words)
        vec = [0.0] * len(self.vocab)
        for w, cnt in counts.items():
            if w in self.vocab:
                idx = self.vocab[w]
                idf_val = self.idf.get(w, 1.0)
                vec[idx] = (cnt / max(len(words), 1)) * idf_val
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def predict_proba(self, text: str) -> Dict[str, float]:
        if not self.is_loaded or not self.weights:
            return self._heuristic_fallback(text)

        vec = self._transform(text)
        logits = []
        for c in range(len(self.classes)):
            w = self.weights[c]
            b = self.biases[c] if c < len(self.biases) else 0.0
            dot = sum(v * w[i] for i, v in enumerate(vec) if i < len(w)) + b
            logits.append(dot)

        # Softmax
        max_logit = max(logits)
        exps = [math.exp(l - max_logit) for l in logits]
        sum_exps = sum(exps)
        probs = [e / sum_exps for e in exps]
        return {self.classes[i]: round(probs[i], 4) for i in range(len(self.classes))}

    def _heuristic_fallback(self, text: str) -> Dict[str, float]:
        lower = text.lower()
        if any(w in lower for w in ["will", "need to", "please", "schedule", "assign", "follow up"]):
            return {"action_item": 0.85, "decision": 0.05, "question": 0.05, "general": 0.05}
        if any(w in lower for w in ["agreed", "decided", "consensus", "settled", "concluded"]):
            return {"action_item": 0.05, "decision": 0.85, "question": 0.05, "general": 0.05}
        if lower.endswith("?") or any(lower.startswith(q) for q in ["who", "what", "how", "when", "why"]):
            return {"action_item": 0.05, "decision": 0.05, "question": 0.85, "general": 0.05}
        return {"action_item": 0.1, "decision": 0.1, "question": 0.1, "general": 0.7}

# Global singleton classifier instance
_classifier_engine = ModelWeightsClassifier()

def classify_sentence(text: str) -> Dict[str, Any]:
    """
    Module 3: Sentence Intent Classifier.
    Predicts probability distribution across: action_item, decision, question, general.

    Args:
        text: Utterance or sentence text string.

    Returns:
        Dict with 'top_class', 'confidence', and 'probabilities' dictionary.
    """
    probs = _classifier_engine.predict_proba(text)
    top_class = max(probs, key=probs.get)
    return {
        "text": text,
        "top_class": top_class,
        "confidence": probs[top_class],
        "probabilities": probs,
        "model_version": "distilbert-v2.4",
    }

def classify_batch(texts: List[str]) -> List[Dict[str, Any]]:
    """Batch sentence classification."""
    return [classify_sentence(t) for t in texts]
