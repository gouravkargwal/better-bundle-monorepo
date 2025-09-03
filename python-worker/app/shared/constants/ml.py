"""
ML constants for BetterBundle Python Worker
"""

# ML model types
ML_MODEL_TYPES = [
    "recommendation",
    "classification",
    "regression",
    "clustering",
    "ensemble",
]

# ML training statuses
ML_TRAINING_STATUSES = [
    "pending",
    "training",
    "completed",
    "failed",
    "cancelled",
]

# ML model statuses
ML_MODEL_STATUSES = [
    "training",
    "trained",
    "deployed",
    "failed",
    "archived",
]

# Feature engineering settings
FEATURE_ENGINEERING_SETTINGS = {
    "max_features_per_entity": 100,
    "feature_quality_threshold": 0.7,
    "categorical_encoding_method": "label_encoding",
    "numerical_scaling_method": "standard_scaling",
    "missing_value_strategy": "imputation",
}

# Gorse ML settings
GORSE_ML_SETTINGS = {
    "default_timeout": 60,
    "max_retries": 3,
    "batch_size": 1000,
    "model_update_frequency": "daily",
}

# ML pipeline configurations
ML_PIPELINE_CONFIGS = {
    "recommendation": {
        "algorithm": "collaborative_filtering",
        "similarity_metric": "cosine",
        "neighborhood_size": 75,
        "min_rating": 1,
        "max_rating": 5,
    },
    "classification": {
        "algorithm": "random_forest",
        "n_estimators": 150,
        "max_depth": 15,
        "random_state": 42,
    },
    "regression": {
        "algorithm": "gradient_boosting",
        "n_estimators": 150,
        "learning_rate": 0.05,
        "max_depth": 8,
    },
}

# Feature types
FEATURE_TYPES = [
    "numerical",
    "categorical",
    "temporal",
    "text",
    "image",
    "geospatial",
]

# Model evaluation metrics
MODEL_EVALUATION_METRICS = {
    "classification": ["accuracy", "precision", "recall", "f1_score", "auc"],
    "regression": ["mse", "rmse", "mae", "r2_score", "mape"],
    "recommendation": ["precision_at_k", "recall_at_k", "ndcg", "map"],
}

# Hyperparameter optimization
HYPERPARAMETER_OPTIMIZATION = {
    "method": "grid_search",
    "cv_folds": 5,
    "n_trials": 100,
    "timeout": 3600,
}

__all__ = [
    "ML_MODEL_TYPES",
    "ML_TRAINING_STATUSES",
    "ML_MODEL_STATUSES",
    "FEATURE_ENGINEERING_SETTINGS",
    "GORSE_ML_SETTINGS",
    "ML_PIPELINE_CONFIGS",
    "FEATURE_TYPES",
    "MODEL_EVALUATION_METRICS",
    "HYPERPARAMETER_OPTIMIZATION",
]
