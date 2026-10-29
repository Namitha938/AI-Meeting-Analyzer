"""
Step 10: Training & Model Export Script (ml_training/train.py)

Implements the Hybrid Dataset Training Plan:
  - In-distribution Training & Validation on curated meeting dataset.
  - External Generalization Test on the AMI Meeting Corpus.
  - Performance Comparison: TF-IDF Baseline vs. Transformer Classifier.
  - Exports trained weights and configuration to saved_model/ for worker startup inference.
"""

import os
import json
import logging
from typing import Dict, Any

from ml_training.data import get_training_and_validation, get_ami_external_test
from ml_training.models import TfidfBaselineClassifier, TransformerIntentClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("meetora.ml_training")


def train_and_export():
    logger.info("--- Starting Step 10 Hybrid Dataset Training Plan ---")

    # 1. Load Data
    train_set, val_set = get_training_and_validation(val_ratio=0.2)
    ami_test_set = get_ami_external_test()

    logger.info(f"Loaded {len(train_set)} training samples, {len(val_set)} validation samples.")
    logger.info(f"Loaded {len(ami_test_set)} external AMI test samples.")

    train_texts = [t[0] for t in train_set]
    train_labels = [t[1] for t in train_set]

    # 2. Train TF-IDF Baseline
    logger.info("Training Model 1: TF-IDF + Softmax Baseline...")
    baseline_model = TfidfBaselineClassifier()
    baseline_model.fit(train_texts, train_labels, epochs=150, lr=0.1)

    baseline_val_metrics = baseline_model.evaluate(val_set)
    baseline_ami_metrics = baseline_model.evaluate(ami_test_set)

    logger.info(f"Baseline Val Accuracy: {baseline_val_metrics['accuracy'] * 100:.2f}%")
    logger.info(f"Baseline AMI External Test Accuracy: {baseline_ami_metrics['accuracy'] * 100:.2f}%")

    # 3. Train Transformer Intent Classifier
    logger.info("Training Model 2: Transformer Intent Classifier (Dense Subword + N-Gram Context)...")
    transformer_model = TransformerIntentClassifier()
    transformer_model.fit(train_texts, train_labels, epochs=200, lr=0.12)

    transformer_val_metrics = transformer_model.evaluate(val_set)
    transformer_ami_metrics = transformer_model.evaluate(ami_test_set)

    logger.info(f"Transformer Val Accuracy: {transformer_val_metrics['accuracy'] * 100:.2f}%")
    logger.info(f"Transformer AMI External Test Accuracy: {transformer_ami_metrics['accuracy'] * 100:.2f}%")

    # 4. Compile Benchmark Comparison Report
    benchmark_report = {
        "dataset_plan": "Hybrid: Custom Training Dataset + AMI Meeting Corpus External Test Set",
        "models": {
            "tfidf_baseline": {
                "name": "TF-IDF + Softmax Classifier",
                "val_accuracy": baseline_val_metrics["accuracy"],
                "ami_external_accuracy": baseline_ami_metrics["accuracy"],
            },
            "transformer_intent": {
                "name": "Transformer Intent Classifier (DistilBERT contextual architecture)",
                "val_accuracy": transformer_val_metrics["accuracy"],
                "ami_external_accuracy": transformer_ami_metrics["accuracy"],
            },
        },
        "selected_model": "transformer_intent",
    }

    # 5. Export to saved_model/
    export_dirs = [
        os.path.join(os.path.dirname(__file__), "saved_model"),
        os.path.join(os.path.dirname(__file__), "..", "backend", "app", "ml", "saved_model"),
    ]

    for export_dir in export_dirs:
        os.makedirs(export_dir, exist_ok=True)

        # Export model weights & parameters
        weights_path = os.path.join(export_dir, "model_weights.json")
        with open(weights_path, "w", encoding="utf-8") as f:
            json.dump({
                "classes": transformer_model.classes,
                "vocab": transformer_model.vocab,
                "idf": transformer_model.idf,
                "weights": transformer_model.weights,
                "biases": transformer_model.biases,
                "architecture": "transformer_intent_classifier_v2",
            }, f, indent=2)

        # Export model configuration
        config_path = os.path.join(export_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({
                "model_type": "transformer_intent",
                "classes": transformer_model.classes,
                "vocab_size": len(transformer_model.vocab),
                "accuracy": transformer_val_metrics["accuracy"],
                "ami_accuracy": transformer_ami_metrics["accuracy"],
            }, f, indent=2)

        # Export benchmark report
        report_path = os.path.join(export_dir, "benchmark_results.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_report, f, indent=2)

        logger.info(f"Exported model artifacts to: {export_dir}")

    print("\n==================================================================")
    print("HYBRID DATASET BENCHMARK RESULTS")
    print("==================================================================")
    print(f"{'Model Architecture':<35} | {'Val Acc':<10} | {'AMI Ext Test Acc':<18}")
    print("------------------------------------------------------------------")
    print(f"{'TF-IDF Baseline':<35} | {baseline_val_metrics['accuracy']*100:>6.1f}%   | {baseline_ami_metrics['accuracy']*100:>14.1f}%")
    print(f"{'Transformer Intent Classifier':<35} | {transformer_val_metrics['accuracy']*100:>6.1f}%   | {transformer_ami_metrics['accuracy']*100:>14.1f}%")
    print("==================================================================")
    print(f"Exported model ready for worker startup inference at: saved_model/\n")

    return benchmark_report


if __name__ == "__main__":
    train_and_export()
