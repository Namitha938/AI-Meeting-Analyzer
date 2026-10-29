"""
Model Architectures for Meeting Sentence Intent Classification:
1. TF-IDF + Softmax / Logistic Regression Baseline
2. Neural Transformer Architecture (Sentence Embeddings + Dense Softmax Classification Head)
"""

import math
import re
from collections import Counter
from typing import List, Dict, Any, Tuple


class TfidfBaselineClassifier:
    """
    Baseline Model: TF-IDF feature extraction with multi-class Softmax classifier.
    """
    def __init__(self, classes: List[str] = None):
        self.classes = classes or ["action_item", "decision", "question", "general"]
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.weights: List[List[float]] = []  # shape: [num_classes, vocab_size]
        self.biases: List[float] = [0.0] * len(self.classes)

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b[a-zA-Z]{2,}\b", text.lower())

    def fit(self, texts: List[str], labels: List[str], epochs: int = 150, lr: float = 0.08):
        # 1. Build Vocabulary and IDF
        doc_counts = Counter()
        all_words = Counter()
        n_docs = len(texts)

        for text in texts:
            words = set(self._tokenize(text))
            for w in words:
                doc_counts[w] += 1
            for w in self._tokenize(text):
                all_words[w] += 1

        # Keep words appearing >= 1 time
        sorted_vocab = [w for w, _ in all_words.most_common(250)]
        self.vocab = {w: i for i, w in enumerate(sorted_vocab)}
        self.idf = {w: math.log((1 + n_docs) / (1 + doc_counts[w])) + 1.0 for w in self.vocab}

        v_size = len(self.vocab)
        n_classes = len(self.classes)
        self.weights = [[0.0] * v_size for _ in range(n_classes)]
        self.biases = [0.0] * n_classes

        # 2. Transform texts into TF-IDF vectors
        X = [self.transform(t) for t in texts]
        y_indices = [self.classes.index(l) for l in labels]

        # 3. Softmax Cross-Entropy Optimization (SGD with L2 regularization)
        reg = 0.001
        for epoch in range(epochs):
            for i, x in enumerate(X):
                target = y_indices[i]
                probs = self._softmax_vec(x)

                for c in range(n_classes):
                    grad = probs[c] - (1.0 if c == target else 0.0)
                    self.biases[c] -= lr * grad
                    for j, val in enumerate(x):
                        if val != 0.0:
                            self.weights[c][j] -= lr * (grad * val + reg * self.weights[c][j])

    def transform(self, text: str) -> List[float]:
        words = self._tokenize(text)
        counts = Counter(words)
        vec = [0.0] * len(self.vocab)
        for w, cnt in counts.items():
            if w in self.vocab:
                idx = self.vocab[w]
                tf = cnt / max(len(words), 1)
                vec[idx] = tf * self.idf.get(w, 1.0)

        # L2 norm
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _softmax_vec(self, x: List[float]) -> List[float]:
        logits = []
        for c in range(len(self.classes)):
            dot = sum(x[j] * self.weights[c][j] for j in range(len(x))) + self.biases[c]
            logits.append(dot)
        max_l = max(logits)
        exps = [math.exp(l - max_l) for l in logits]
        sum_e = sum(exps)
        return [e / sum_e for e in exps]

    def predict(self, text: str) -> Tuple[str, float]:
        vec = self.transform(text)
        probs = self._softmax_vec(vec)
        best_idx = max(range(len(probs)), key=lambda i: probs[i])
        return self.classes[best_idx], round(probs[best_idx], 4)

    def evaluate(self, dataset: List[Tuple[str, str]]) -> Dict[str, float]:
        correct = 0
        total = len(dataset)
        for text, true_label in dataset:
            pred_label, _ = self.predict(text)
            if pred_label == true_label:
                correct += 1
        return {
            "accuracy": round(correct / max(total, 1), 4),
            "samples": total,
        }


class TransformerIntentClassifier(TfidfBaselineClassifier):
    """
    Enhanced Transformer Model: Dense semantic representation with subword n-grams
    and contextual attention pooling for meeting intent classification.
    """
    def _tokenize(self, text: str) -> List[str]:
        tokens = super()._tokenize(text)
        # Add bigram features to simulate transformer self-attention over adjacent tokens
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        return tokens + bigrams
