"""
Responsible AI Demo
AIF-C01 Exam Prep — Session 15

Covers:
  - Bias audit: detecting disparate model performance across demographic groups
  - SHAP: global feature importance + per-prediction waterfall explanation
  - LIME: local surrogate explanation for one prediction
  - Model card: structured documentation of intended use, performance, limitations

All data is synthetic — no PHI. Synthetic loan applicant data only.
"""

import warnings

warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402

matplotlib.use("Agg")  # non-interactive backend — must be set before pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402
from lime.lime_tabular import LimeTabularExplainer  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import accuracy_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Synthetic Dataset
#
# We simulate a loan approval dataset with a deliberate demographic imbalance.
# Group A (majority) has stronger financial profiles in the training data —
# this models the real-world pattern where historical data encodes past bias.
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: Generating synthetic loan dataset")
print("=" * 60)

np.random.seed(42)
n = 2000

# Group 0 = majority group, Group 1 = minority group
# Minority group has noisier / weaker financial features in training data
# This is data bias baked in intentionally to demonstrate detection
group = np.random.choice([0, 1], size=n, p=[0.70, 0.30])

# Financial features — minority group has slightly worse mean values
# due to the synthetic historical bias we're encoding
credit_score = np.where(
    group == 0,
    np.random.normal(680, 60, n),  # majority: mean 680
    np.random.normal(
        640, 70, n
    ),  # minority: mean 640 (encoded historical disadvantage)
)
income = np.where(
    group == 0,
    np.random.normal(75000, 20000, n),
    np.random.normal(58000, 18000, n),
)
debt_ratio = np.where(
    group == 0,
    np.random.normal(0.30, 0.10, n),
    np.random.normal(0.38, 0.12, n),
)
employment_years = np.where(
    group == 0,
    np.random.normal(8, 4, n),
    np.random.normal(5, 3, n),
)
loan_amount = np.random.normal(25000, 10000, n)

# Label: approved (1) if credit score > 620 AND debt ratio < 0.5
# This threshold produces higher approval for group 0 due to the feature gap above.
# We add 10% label noise to prevent the model from achieving perfect accuracy —
# real datasets always have noise, and perfect accuracy would hide the bias signal.
approved = ((credit_score > 620) & (debt_ratio < 0.50)).astype(int)
noise_mask = np.random.random(n) < 0.10  # flip 10% of labels
approved = (approved ^ noise_mask).astype(int)

df = pd.DataFrame(
    {
        "credit_score": credit_score,
        "income": income,
        "debt_ratio": debt_ratio,
        "employment_years": employment_years,
        "loan_amount": loan_amount,
        "group": group,  # demographic attribute — NOT used as a feature
        "approved": approved,
    }
)

feature_cols = [
    "credit_score",
    "income",
    "debt_ratio",
    "employment_years",
    "loan_amount",
]
# Note: 'group' is deliberately excluded from features — the model should NOT
# use demographic membership directly. But bias can still enter through proxy features.

print(f"Dataset: {len(df)} applicants")
print(f"Group 0 (majority): {(group == 0).sum()} applicants")
print(f"Group 1 (minority): {(group == 1).sum()} applicants")
print(f"Overall approval rate: {approved.mean():.1%}")
print(f"Group 0 approval rate: {df[df.group == 0].approved.mean():.1%}")
print(f"Group 1 approval rate: {df[df.group == 1].approved.mean():.1%}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Train Model + Bias Audit
#
# We train a Random Forest on features only (no group column), then measure
# accuracy separately for each demographic group. If performance differs
# significantly, the model has disparate impact — a fairness failure.
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Train model and bias audit")
print("=" * 60)

X = df[feature_cols].values
y = df["approved"].values
groups = df["group"].values

X_train, X_test, y_train, y_test, g_train, g_test = train_test_split(
    X, y, groups, test_size=0.25, random_state=42
)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
overall_acc = accuracy_score(y_test, y_pred)

# Bias audit: split test set by group, compute accuracy for each
mask_0 = g_test == 0
mask_1 = g_test == 1

acc_group0 = accuracy_score(y_test[mask_0], y_pred[mask_0])
acc_group1 = accuracy_score(y_test[mask_1], y_pred[mask_1])

print(f"Overall accuracy:       {overall_acc:.3f}")
print(f"Accuracy — Group 0:     {acc_group0:.3f}")
print(f"Accuracy — Group 1:     {acc_group1:.3f}")
print(f"Accuracy gap:           {abs(acc_group0 - acc_group1):.3f}")

if abs(acc_group0 - acc_group1) > 0.05:
    print("⚠  BIAS DETECTED: accuracy gap exceeds 5% threshold")
else:
    print("✓  No significant accuracy gap detected")

# Visualise the bias audit
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Left: approval rates by group
axes[0].bar(
    ["Group 0\n(majority)", "Group 1\n(minority)"],
    [df[df.group == 0].approved.mean(), df[df.group == 1].approved.mean()],
    color=["steelblue", "salmon"],
    width=0.5,
)
axes[0].set_ylim(0, 1)
axes[0].set_ylabel("Approval Rate")
axes[0].set_title("Training Data: Approval Rate by Group\n(data bias visible)")
for i, v in enumerate(
    [df[df.group == 0].approved.mean(), df[df.group == 1].approved.mean()]
):
    axes[0].text(i, v + 0.02, f"{v:.1%}", ha="center", fontsize=12)

# Right: model accuracy by group
axes[1].bar(
    ["Group 0\n(majority)", "Group 1\n(minority)"],
    [acc_group0, acc_group1],
    color=["steelblue", "salmon"],
    width=0.5,
)
axes[1].set_ylim(0, 1)
axes[1].set_ylabel("Model Accuracy")
axes[1].set_title("Model Performance by Group\n(disparate impact = fairness failure)")
for i, v in enumerate([acc_group0, acc_group1]):
    axes[1].text(i, v + 0.02, f"{v:.1%}", ha="center", fontsize=12)

plt.tight_layout()
plt.savefig("ml-fundamentals/bias_audit.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: bias_audit.png")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: SHAP Explanation
#
# TreeExplainer is the fast path for tree-based models (Random Forest, XGBoost).
# It computes exact Shapley values — not approximations — by exploiting the
# tree structure. For each prediction, every feature gets a positive or negative
# contribution score showing how much it pushed the prediction up or down.
#
# shap_values shape: (n_samples, n_features, n_classes)
# We take index [1] for the positive class (approved=1).
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: SHAP — global + local explanation")
print("=" * 60)

explainer = shap.TreeExplainer(model)
# Use a sample of test set to keep runtime reasonable
sample_idx = np.random.choice(len(X_test), size=200, replace=False)
X_sample = X_test[sample_idx]
shap_values = explainer.shap_values(X_sample)

# SHAP >= 0.46 returns a 3D array (n_samples, n_features, n_classes) for classifiers.
# Older versions returned a list [class0_array, class1_array].
# We always want the class-1 (approved) slice.
if isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
    shap_vals_approved = shap_values[:, :, 1]  # shape: (n_samples, n_features)
    base_value = (
        explainer.expected_value[1]
        if hasattr(explainer.expected_value, "__len__")
        else explainer.expected_value
    )
else:
    shap_vals_approved = shap_values[1]
    base_value = (
        explainer.expected_value[1]
        if hasattr(explainer.expected_value, "__len__")
        else explainer.expected_value
    )

print("SHAP global feature importance (mean |SHAP value|):")
mean_abs_shap = np.abs(shap_vals_approved).mean(axis=0)
for feat, val in sorted(zip(feature_cols, mean_abs_shap), key=lambda x: -x[1]):
    bar = "█" * int(val * 200)
    print(f"  {feat:<20} {val:.4f}  {bar}")

# Global summary plot — each dot is one prediction coloured by feature value
# Position on x-axis = SHAP value (how much it changed the prediction)
fig, ax = plt.subplots(figsize=(10, 5))
shap.summary_plot(
    shap_vals_approved,
    X_sample,
    feature_names=feature_cols,
    show=False,
    plot_size=None,
)
plt.title(
    "SHAP Summary — Loan Approval Model\n"
    "(each dot = one prediction; colour = feature value)"
)
plt.tight_layout()
plt.savefig("ml-fundamentals/shap_summary.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: shap_summary.png")

# Waterfall plot for one specific prediction
# Waterfall: base value (average prediction) + each feature's contribution = final score
print("\nSHAP waterfall for test applicant #0:")
explanation = shap.Explanation(
    values=shap_vals_approved[0],
    base_values=base_value,
    data=X_sample[0],
    feature_names=feature_cols,
)
shap.waterfall_plot(explanation, show=False)
plt.title("SHAP Waterfall — Single Applicant Explanation")
plt.tight_layout()
plt.savefig("ml-fundamentals/shap_waterfall.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: shap_waterfall.png")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: LIME Explanation
#
# LIME works differently from SHAP: it perturbs the input (randomly changes
# feature values), runs each perturbed version through the black-box model,
# then fits a simple linear regression on the (perturbed inputs → predictions)
# pairs. The linear model's coefficients become the explanation.
#
# This is a local approximation — it only describes the model's behaviour
# near this specific input, not globally. Run it twice, you may get slightly
# different coefficients (instability is a known LIME limitation).
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: LIME — local surrogate explanation")
print("=" * 60)

lime_explainer = LimeTabularExplainer(
    X_train,
    feature_names=feature_cols,
    class_names=["Denied", "Approved"],
    mode="classification",
    random_state=42,
)

# Explain the same applicant we used for SHAP waterfall
instance = X_test[0]
lime_exp = lime_explainer.explain_instance(
    instance,
    model.predict_proba,
    num_features=5,
)

prob_approved = model.predict_proba([instance])[0][1]
print(f"Model prediction probability: Approved={prob_approved:.3f}")
print("LIME feature contributions (local linear approximation):")
for feat, weight in lime_exp.as_list():
    direction = "▲" if weight > 0 else "▼"
    print(f"  {direction} {feat:<35} weight={weight:+.4f}")

fig = lime_exp.as_pyplot_figure()
plt.title(
    "LIME Explanation — Single Applicant\n"
    "(local linear approximation around this input)"
)
plt.tight_layout()
plt.savefig("ml-fundamentals/lime_explanation.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: lime_explanation.png")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Model Card
#
# A model card is a structured document that ships with the model.
# It answers: what is this for, how does it perform across subgroups,
# what are the known limitations, and who is accountable.
# AWS SageMaker Model Cards follow this same structure.
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Model Card")
print("=" * 60)

model_card = {
    "model_name": "Loan Approval Classifier v1.0",
    "model_type": "RandomForestClassifier (n_estimators=100)",
    "intended_use": (
        "Assist loan officers in initial screening of applications. "
        "Provides a probability score; final approval requires human review."
    ),
    "out_of_scope": [
        "Automated approval without human oversight",
        "Applicants outside the original training distribution",
        "Use as sole decision-maker for credit denial",
    ],
    "training_data": {
        "source": "Synthetic — generated for demo purposes",
        "size": f"{len(X_train)} training samples",
        "features": feature_cols,
        "label": "approved (1) / denied (0)",
        "sensitive_attributes_excluded": ["group (demographic membership)"],
    },
    "performance": {
        "overall_accuracy": f"{overall_acc:.3f}",
        "accuracy_group_0_majority": f"{acc_group0:.3f}",
        "accuracy_group_1_minority": f"{acc_group1:.3f}",
        "accuracy_gap": f"{abs(acc_group0 - acc_group1):.3f}",
        "fairness_flag": abs(acc_group0 - acc_group1) > 0.05,
    },
    "known_limitations": [
        "Training data encodes historical approval patterns — may reflect past bias",
        "Proxy variables (income, zip code) can carry demographic signal indirectly",
        "LIME is locally unstable — re-running may yield different feature weights",
        "Model not validated on applicants outside the synthetic distribution",
    ],
    "explainability": {
        "method": "SHAP TreeExplainer (global) + LIME (local per-prediction)",
        "top_feature_by_shap": feature_cols[int(mean_abs_shap.argmax())],
    },
    "governance": {
        "owner": "ML Platform Team",
        "review_cadence": "Quarterly bias audit required",
        "human_oversight": "Required — model score is advisory only",
        "audit_trail": "All predictions logged with applicant ID and model version",
    },
}

print("\n--- MODEL CARD ---")
for section, content in model_card.items():
    print(f"\n[{section.upper()}]")
    if isinstance(content, dict):
        for k, v in content.items():
            print(f"  {k}: {v}")
    elif isinstance(content, list):
        for item in content:
            print(f"  - {item}")
    else:
        print(f"  {content}")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SUMMARY — Responsible AI Demo")
print("=" * 60)
print(f"  Bias audit:   accuracy gap = {abs(acc_group0 - acc_group1):.3f}")
print(f"  SHAP top feature: {feature_cols[int(mean_abs_shap.argmax())]}")
print("  LIME: local explanation generated for applicant #0")
print(f"  Model card: fairness_flag = {model_card['performance']['fairness_flag']}")
print("\nCharts saved:")
print("  bias_audit.png       — disparate impact visualisation")
print("  shap_summary.png     — global SHAP feature importance")
print("  shap_waterfall.png   — single-prediction SHAP breakdown")
print("  lime_explanation.png — single-prediction LIME breakdown")
