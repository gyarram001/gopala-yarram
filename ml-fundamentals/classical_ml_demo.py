"""
Classical ML Fundamentals Demo
AIF-C01 Exam Prep — Item 12

Covers:
  - Supervised vs unsupervised learning
  - Logistic regression, decision tree, random forest, k-means
  - Confusion matrix: accuracy, precision, recall, F1, AUC-ROC
  - Overfitting vs underfitting — visual proof
  - Bias-variance tradeoff
  - Regression: RMSE and MAE

All data is synthetic — no PHI.
"""

import numpy as np
import matplotlib

matplotlib.use(
    "Agg"
)  # non-interactive backend — saves to file instead of opening window
import matplotlib.pyplot as plt
from sklearn.datasets import make_classification, make_regression, make_blobs
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
    mean_squared_error,
    mean_absolute_error,
)
import warnings

warnings.filterwarnings("ignore")

np.random.seed(42)  # reproducibility — same "random" data every run

DIVIDER = "\n" + "=" * 65 + "\n"


# ─────────────────────────────────────────────────────────────────
# SECTION 1: Generate synthetic claim denial data
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 1: THE LABELED DATASET")
print(DIVIDER)

# make_classification creates a realistic labeled dataset.
# n_samples=1000    → 1,000 historical claims
# n_features=10     → 10 input columns (payer code, amount, service type, etc.)
# weights=[0.94, 0.06] → 94% NOT denied, 6% denied — realistic class imbalance
# n_informative=5   → only 5 of the 10 features actually predict denial;
#                     the other 5 are noise (just like real data)
X, y = make_classification(
    n_samples=1000,
    n_features=10,
    n_informative=5,
    n_redundant=2,
    weights=[0.94, 0.06],  # imbalanced: 94% class 0, 6% class 1
    random_state=42,
)

print(f"Dataset shape: {X.shape}")
print(f"  → {X.shape[0]} claims, {X.shape[1]} features per claim\n")

# Count the labels — this is what we "already know" from historical records
unique, counts = np.unique(y, return_counts=True)
print("Label distribution (what we're teaching the model to predict):")
for label, count in zip(unique, counts):
    name = "NOT denied" if label == 0 else "DENIED"
    pct = count / len(y) * 100
    print(f"  y={label} ({name}): {count} claims  ({pct:.1f}%)")

print(
    f"\nIf a model always predicts 'not denied', accuracy = {counts[0]/len(y)*100:.1f}%"
)
print("→ That's why accuracy alone is misleading on imbalanced data.")


# ─────────────────────────────────────────────────────────────────
# SECTION 2: Train / Validation / Test split
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 2: TRAIN / VALIDATION / TEST SPLIT")
print(DIVIDER)

# First split: carve out the test set — lock it away, never touch until final eval
# stratify=y → preserves the 94/6 imbalance ratio in both halves.
# Without this, by chance you could get a test set with 0% denials.
X_temp, X_test, y_temp, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

# Second split: from the remaining 80%, split training from validation
X_train, X_val, y_train, y_val = train_test_split(
    X_temp,
    y_temp,
    test_size=0.25,
    random_state=42,
    stratify=y_temp,
    # 0.25 × 0.80 = 0.20 of total → final split: 60% train, 20% val, 20% test
)

print(f"Training set:   {len(X_train)} claims  ← model learns from this")
print(f"Validation set: {len(X_val)} claims  ← we tune hyperparameters here")
print(f"Test set:       {len(X_test)} claims  ← final honest evaluation, touch ONCE")
print(f"\nDenial rate in training set: {y_train.mean()*100:.1f}%")
print(f"Denial rate in test set:     {y_test.mean()*100:.1f}%")
print("→ stratify=y kept the imbalance consistent across splits")


# ─────────────────────────────────────────────────────────────────
# SECTION 3: Logistic Regression — baseline model
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 3: LOGISTIC REGRESSION")
print(DIVIDER)

print("What logistic regression does:")
print("  Fits a line through the feature space that best separates")
print("  'denied' from 'not denied'. Outputs a probability (0–1).")
print("  Threshold: if P(denied) >= 0.5 → predict denied.\n")

# class_weight="balanced" tells sklearn to give more weight to the minority class
# (denials) during training. Without this, the model can hit 94% accuracy by
# just predicting "not denied" every time. This is the imbalance fix.
lr_model = LogisticRegression(
    class_weight="balanced",  # compensates for 94/6 imbalance
    max_iter=1000,
    random_state=42,
)
lr_model.fit(X_train, y_train)

# Predict on the TEST set — first honest look at real performance
y_pred_lr = lr_model.predict(X_test)

# ── Confusion Matrix ──────────────────────────────────────────────
cm = confusion_matrix(y_test, y_pred_lr)
tn, fp, fn, tp = cm.ravel()

print("CONFUSION MATRIX:")
print("                   Predicted NOT denied   Predicted DENIED")
print(f"  Actual NOT denied       {tn:>4}                  {fp:>4}")
print(f"  Actual DENIED           {fn:>4}                  {tp:>4}")
print()
print(f"  True Negatives  (TN): {tn}  → correctly said 'not denied'")
print(f"  False Positives (FP): {fp}  → said 'denied' but wasn't  (false alarm)")
print(
    f"  False Negatives (FN): {fn}   → said 'not denied' but WAS denied  (missed denial)"
)
print(f"  True Positives  (TP): {tp}   → correctly caught a denial")

# ── All metrics ───────────────────────────────────────────────────
acc = accuracy_score(y_test, y_pred_lr)
prec = precision_score(y_test, y_pred_lr, zero_division=0)
rec = recall_score(y_test, y_pred_lr, zero_division=0)
f1 = f1_score(y_test, y_pred_lr, zero_division=0)

# AUC needs probabilities, not just class predictions
y_prob_lr = lr_model.predict_proba(X_test)[:, 1]  # P(denied) for each claim
auc = roc_auc_score(y_test, y_prob_lr)

print("\nMETRICS:")
print(
    f"  Accuracy  = (TP+TN)/(total)       = {acc:.3f}  ← misleading on imbalanced data"
)
print(
    f"  Precision = TP/(TP+FP)             = {prec:.3f}  ← of flagged denials, {prec*100:.0f}% were real"
)
print(
    f"  Recall    = TP/(TP+FN)             = {rec:.3f}  ← caught {rec*100:.0f}% of all actual denials"
)
print(f"  F1 Score  = harmonic mean(P, R)    = {f1:.3f}  ← balanced single number")
print(f"  AUC-ROC   = area under ROC curve   = {auc:.3f}  ← 0.5=random, 1.0=perfect")

print("\nBusiness interpretation:")
print(f"  We caught {tp} out of {tp+fn} actual denials.")
print(f"  We missed {fn} denials (false negatives) — those hit us as denied claims.")
print(
    f"  We false-alarmed on {fp} claims (false positives) — wasted prior auth effort."
)


# ─────────────────────────────────────────────────────────────────
# SECTION 4: Decision Tree — overfitting proof
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 4: DECISION TREE — OVERFITTING PROOF")
print(DIVIDER)

print("What a decision tree does:")
print("  Learns a series of if/else splits on features.")
print("  Example: if amount > 45000 AND payer=Aetna → likely denied.")
print("  Each split reduces 'impurity' — mixed labels in a node.\n")

# max_depth=None → unlimited depth. The tree will grow until it
# has memorized every single training example perfectly.
# This is textbook overfitting.
tree_overfit = DecisionTreeClassifier(
    max_depth=None,  # unlimited — will memorize training data
    class_weight="balanced",
    random_state=42,
)
tree_overfit.fit(X_train, y_train)

train_acc_overfit = accuracy_score(y_train, tree_overfit.predict(X_train))
test_acc_overfit = accuracy_score(y_test, tree_overfit.predict(X_test))
test_f1_overfit = f1_score(y_test, tree_overfit.predict(X_test), zero_division=0)

print("Unlimited depth tree:")
print(
    f"  Training accuracy: {train_acc_overfit:.3f}  ← near perfect (memorized training data)"
)
print(f"  Test accuracy:     {test_acc_overfit:.3f}  ← drops on new data")
print(f"  Test F1:           {test_f1_overfit:.3f}")
print(f"  Tree depth:        {tree_overfit.get_depth()} levels deep!")
print(f"\n  GAP (train - test): {train_acc_overfit - test_acc_overfit:.3f}")
print("  → This gap IS the overfit. Model memorized noise in training data.")

# Fix: limit max_depth. Forces the tree to learn general patterns, not memorize.
# max_depth=5 means at most 5 levels of if/else splits.
tree_fixed = DecisionTreeClassifier(
    max_depth=5,  # constrained — learns patterns, not noise
    class_weight="balanced",
    random_state=42,
)
tree_fixed.fit(X_train, y_train)

train_acc_fixed = accuracy_score(y_train, tree_fixed.predict(X_train))
test_acc_fixed = accuracy_score(y_test, tree_fixed.predict(X_test))
test_f1_fixed = f1_score(y_test, tree_fixed.predict(X_test), zero_division=0)

print("\nDepth=5 tree (regularized):")
print(f"  Training accuracy: {train_acc_fixed:.3f}")
print(f"  Test accuracy:     {test_acc_fixed:.3f}  ← improved or maintained")
print(f"  Test F1:           {test_f1_fixed:.3f}")
print(
    f"  GAP (train - test): {train_acc_fixed - test_acc_fixed:.3f}  ← smaller gap = less overfit"
)

# Visualize overfitting by sweeping max_depth values
depths = range(1, 25)
train_scores, test_scores = [], []
for d in depths:
    t = DecisionTreeClassifier(max_depth=d, class_weight="balanced", random_state=42)
    t.fit(X_train, y_train)
    train_scores.append(accuracy_score(y_train, t.predict(X_train)))
    test_scores.append(accuracy_score(y_test, t.predict(X_test)))

plt.figure(figsize=(10, 5))
plt.plot(depths, train_scores, "b-o", markersize=4, label="Training accuracy")
plt.plot(depths, test_scores, "r-o", markersize=4, label="Test accuracy")
plt.axvline(x=5, color="green", linestyle="--", label="max_depth=5 (sweet spot)")
plt.xlabel("max_depth (model complexity)")
plt.ylabel("Accuracy")
plt.title("Overfitting: Training vs Test Accuracy as Tree Depth Grows")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("ml-fundamentals/overfit_curve.png", dpi=120)
plt.close()
print("\nChart saved: ml-fundamentals/overfit_curve.png")
print("  → Training accuracy rises to 1.0 as depth grows (memorizes data)")
print("  → Test accuracy peaks then falls (learns noise, not patterns)")
print("  → The gap between curves = overfitting")


# ─────────────────────────────────────────────────────────────────
# SECTION 5: Random Forest — why it beats a single tree
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 5: RANDOM FOREST — ENSEMBLE METHOD")
print(DIVIDER)

print("What a random forest does:")
print("  Trains 100 decision trees, each on a random subset of data")
print("  and a random subset of features. Final prediction = majority vote.")
print("  Many high-variance trees averaged together = low variance.\n")

# n_estimators=100 → 100 individual trees
# Each tree sees a random 63% of training rows (bootstrap sampling)
# and a random sqrt(10) ≈ 3 features per split
rf_model = RandomForestClassifier(
    n_estimators=100,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,  # use all CPU cores — each tree trains independently
)
rf_model.fit(X_train, y_train)

y_pred_rf = rf_model.predict(X_test)
y_prob_rf = rf_model.predict_proba(X_test)[:, 1]

rf_prec = precision_score(y_test, y_pred_rf, zero_division=0)
rf_rec = recall_score(y_test, y_pred_rf, zero_division=0)
rf_f1 = f1_score(y_test, y_pred_rf, zero_division=0)
rf_auc = roc_auc_score(y_test, y_prob_rf)
rf_train_acc = accuracy_score(y_train, rf_model.predict(X_train))
rf_test_acc = accuracy_score(y_test, y_pred_rf)

print("MODEL COMPARISON:")
print(f"{'Model':<30} {'Train Acc':>10} {'Test Acc':>10} {'F1':>8} {'AUC':>8}")
print("-" * 68)
print(
    f"{'Logistic Regression':<30} {'N/A':>10} {accuracy_score(y_test, y_pred_lr):>10.3f} {f1:>8.3f} {auc:>8.3f}"
)
print(
    f"{'Decision Tree (unlimited)':<30} {train_acc_overfit:>10.3f} {test_acc_overfit:>10.3f} {test_f1_overfit:>8.3f} {'N/A':>8}"
)
print(
    f"{'Decision Tree (depth=5)':<30} {train_acc_fixed:>10.3f} {test_acc_fixed:>10.3f} {test_f1_fixed:>8.3f} {'N/A':>8}"
)
print(
    f"{'Random Forest (100 trees)':<30} {rf_train_acc:>10.3f} {rf_test_acc:>10.3f} {rf_f1:>8.3f} {rf_auc:>8.3f}"
)

print("\nKey insight:")
print(f"  Random forest train/test gap: {rf_train_acc - rf_test_acc:.3f}")
print(f"  Overfit tree train/test gap:  {train_acc_overfit - test_acc_overfit:.3f}")
print("  → Forest's gap is smaller despite being much more complex")
print("  → Averaging many trees cancels out individual tree errors")

# Feature importance — which inputs actually matter most
importances = rf_model.feature_importances_
top3_idx = np.argsort(importances)[::-1][:3]
print("\nTop 3 most predictive features (out of 10):")
for rank, idx in enumerate(top3_idx, 1):
    print(f"  #{rank}: Feature {idx}  importance={importances[idx]:.3f}")
print("  → Feature importance is a by-product of random forests.")
print("  → In production: feature 0 might be 'payer code', feature 3 = 'amount', etc.")


# ─────────────────────────────────────────────────────────────────
# SECTION 6: ROC Curve and AUC
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 6: AUC-ROC CURVE")
print(DIVIDER)

print("What AUC-ROC means:")
print("  ROC = Receiver Operating Characteristic")
print("  Plots True Positive Rate (recall) vs False Positive Rate")
print("  at every possible decision threshold (not just 0.5).")
print("  AUC = area under that curve.")
print("  AUC=0.5 → random guessing (diagonal line)")
print("  AUC=1.0 → perfect separation\n")

fpr_lr, tpr_lr, _ = roc_curve(y_test, y_prob_lr)
fpr_rf, tpr_rf, _ = roc_curve(y_test, y_prob_rf)

plt.figure(figsize=(7, 6))
plt.plot(
    fpr_lr, tpr_lr, "b-", linewidth=2, label=f"Logistic Regression (AUC={auc:.3f})"
)
plt.plot(fpr_rf, tpr_rf, "r-", linewidth=2, label=f"Random Forest (AUC={rf_auc:.3f})")
plt.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random guess (AUC=0.50)")
plt.xlabel("False Positive Rate (FP / (FP+TN))")
plt.ylabel("True Positive Rate = Recall (TP / (TP+FN))")
plt.title("ROC Curve — Denial Prediction Models")
plt.legend(loc="lower right")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("ml-fundamentals/roc_curve.png", dpi=120)
plt.close()
print("Chart saved: ml-fundamentals/roc_curve.png")
print(f"  Logistic Regression AUC: {auc:.3f}")
print(f"  Random Forest AUC:       {rf_auc:.3f}")
print("  → Higher AUC = better at separating denied from not-denied")
print("  → Curve bows toward top-left = model is better than random")
print("\nWhy AUC beats accuracy here:")
print("  Accuracy rewards the lazy 'always predict 0' model.")
print("  AUC only rewards the model for actually separating the classes.")


# ─────────────────────────────────────────────────────────────────
# SECTION 7: Regression — RMSE and MAE
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 7: REGRESSION METRICS — RMSE AND MAE")
print(DIVIDER)

print("Switching to a regression problem:")
print("  Task: predict claim AMOUNT (a number, not a category)")
print("  This is supervised learning with a continuous output.\n")

# make_regression generates a clean regression dataset
# noise=50.0 → adds realistic variance (real claim amounts aren't perfectly predictable)
X_reg, y_reg = make_regression(n_samples=500, n_features=5, noise=50.0, random_state=42)

X_reg_train, X_reg_test, y_reg_train, y_reg_test = train_test_split(
    X_reg, y_reg, test_size=0.2, random_state=42
)

# Linear regression: fits a straight line (or hyperplane) minimizing
# the sum of squared errors between predictions and true values.
# The "loss function" is Mean Squared Error — why squared?
# Squaring makes large errors much more costly than small ones,
# which is usually what you want (a $10k error is much worse than a $100 error).
lin_reg = LinearRegression()
lin_reg.fit(X_reg_train, y_reg_train)

y_reg_pred = lin_reg.predict(X_reg_test)

rmse = np.sqrt(mean_squared_error(y_reg_test, y_reg_pred))
mae = mean_absolute_error(y_reg_test, y_reg_pred)

print("Linear Regression Results:")
print(f"  RMSE (Root Mean Squared Error): {rmse:.2f}")
print(f"  MAE  (Mean Absolute Error):     {mae:.2f}")
print("\nWhat these numbers mean:")
print(f"  MAE  = on average, predictions are off by {mae:.0f} units")
print(f"  RMSE = {rmse:.0f} units — higher than MAE because RMSE")
print("         penalizes large errors more (they get squared first)")
print("\nWhen to use which:")
print("  RMSE → when large errors are especially costly")
print("          (a $50k claim predicted as $5k is catastrophic)")
print("  MAE  → when all errors matter equally, more robust to outliers")

# Show an actual prediction vs truth sample
print("\nSample predictions vs actuals (first 5):")
print(f"  {'Predicted':>12}  {'Actual':>10}  {'Error':>10}")
for pred, actual in zip(y_reg_pred[:5], y_reg_test[:5]):
    print(f"  {pred:>12.1f}  {actual:>10.1f}  {abs(pred-actual):>10.1f}")


# ─────────────────────────────────────────────────────────────────
# SECTION 8: k-Means — Unsupervised Learning
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 8: k-MEANS CLUSTERING — UNSUPERVISED LEARNING")
print(DIVIDER)

print("Key difference from sections above:")
print("  NO LABELS. We don't tell the model what's 'correct'.")
print("  Task: group members into risk profiles — we don't know them in advance.\n")

# make_blobs creates naturally clustered data (3 groups)
# In reality: member utilization data, no pre-defined risk tiers
X_cluster, _ = make_blobs(n_samples=300, centers=3, cluster_std=1.2, random_state=42)
# _ = true labels discarded — we intentionally ignore them (unsupervised)

# KMeans algorithm:
# 1. Place k centroids randomly
# 2. Assign each point to its nearest centroid
# 3. Move each centroid to the mean of its assigned points
# 4. Repeat until centroid positions stop changing (convergence)
# n_init=10 → run the whole algorithm 10 times with different starting points,
# keep the best result (avoids bad random initialization)
kmeans = KMeans(n_clusters=3, n_init=10, random_state=42)
cluster_labels = kmeans.fit_predict(X_cluster)

# Inertia = sum of squared distances from each point to its centroid.
# Lower = tighter clusters = better fit for this k.
print("k=3 Results:")
print(f"  Inertia (within-cluster sum of squares): {kmeans.inertia_:.1f}")

# Count members in each cluster
for k in range(3):
    n = (cluster_labels == k).sum()
    print(f"  Cluster {k}: {n} members")

# Elbow method — how do you choose k?
# Run k-means for k=1..10, plot inertia. The "elbow" (sharpest bend)
# suggests the best k — beyond it, adding clusters gains little.
inertias = []
k_range = range(1, 11)
for k in k_range:
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    km.fit(X_cluster)
    inertias.append(km.inertia_)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Left: cluster scatter plot
scatter = axes[0].scatter(
    X_cluster[:, 0],
    X_cluster[:, 1],
    c=cluster_labels,
    cmap="viridis",
    alpha=0.6,
    edgecolors="none",
)
axes[0].scatter(
    kmeans.cluster_centers_[:, 0],
    kmeans.cluster_centers_[:, 1],
    s=200,
    c="red",
    marker="X",
    label="Centroids",
    zorder=5,
)
axes[0].set_title("k-Means: Member Risk Clusters (k=3)")
axes[0].set_xlabel("Feature 1 (e.g. utilization)")
axes[0].set_ylabel("Feature 2 (e.g. claim frequency)")
axes[0].legend()

# Right: elbow curve
axes[1].plot(k_range, inertias, "b-o", markersize=6)
axes[1].axvline(x=3, color="red", linestyle="--", label="Elbow at k=3")
axes[1].set_xlabel("Number of clusters (k)")
axes[1].set_ylabel("Inertia (within-cluster sum of squares)")
axes[1].set_title("Elbow Method — Choosing k")
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("ml-fundamentals/kmeans.png", dpi=120)
plt.close()
print("\nChart saved: ml-fundamentals/kmeans.png")
print("  → Left: 3 clusters found with no labels provided")
print("  → Right: elbow at k=3 — inertia drops sharply up to 3,")
print("            then flattens (adding more clusters gains little)")

print("\nSupervised vs Unsupervised — side by side:")
print("  Supervised (logistic regression, decision tree, RF):")
print("    Input: (X, y) — features AND labels")
print("    Output: a function that predicts y for new X")
print("    Requires: labeled historical data")
print("  Unsupervised (k-means):")
print("    Input: just X — no labels")
print("    Output: group assignments (which cluster each point belongs to)")
print("    Requires: only raw data — labels are what you're trying to discover")


# ─────────────────────────────────────────────────────────────────
# SECTION 9: Bias-Variance Tradeoff
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 9: BIAS-VARIANCE TRADEOFF")
print(DIVIDER)

print("The fundamental tension in ML model selection:")
print("  Bias   = systematic error — model consistently wrong in one direction")
print("           High bias = underfitting = model too simple")
print("  Variance = sensitivity to training data — retrain on slightly different")
print("           data and predictions change a lot")
print("           High variance = overfitting = model too complex")
print()
print("  Total Error = Bias² + Variance + Irreducible Noise")
print("  Goal: find the complexity level where Bias² + Variance is minimized\n")

# Demonstrate using cross-validation: measure variance of scores across folds
# A high-variance model will show wildly different scores across folds.
# A high-bias model will show consistently poor scores across folds.

cv_results = {}
models_bv = {
    "Logistic Regression\n(low variance, may have bias)": LogisticRegression(
        class_weight="balanced", max_iter=1000, random_state=42
    ),
    "Decision Tree depth=2\n(high bias, low variance)": DecisionTreeClassifier(
        max_depth=2, class_weight="balanced", random_state=42
    ),
    "Decision Tree unlimited\n(low bias, HIGH variance)": DecisionTreeClassifier(
        max_depth=None, class_weight="balanced", random_state=42
    ),
    "Random Forest\n(low bias, low variance)": RandomForestClassifier(
        n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1
    ),
}

print(f"{'Model':<42} {'Mean F1':>8} {'Std Dev':>8}  Interpretation")
print("-" * 90)

for name, model in models_bv.items():
    # 5-fold cross-validation: train+evaluate 5 times on different data subsets
    # scoring="f1" because our classes are imbalanced
    scores = cross_val_score(model, X_train, y_train, cv=5, scoring="f1")
    one_line_name = name.replace("\n", " ")
    mean_score = scores.mean()
    std_score = scores.std()

    if std_score > 0.15:
        interp = "← high variance (unstable)"
    elif mean_score < 0.25:
        interp = "← high bias (underfits)"
    elif std_score < 0.08 and mean_score > 0.3:
        interp = "← low bias + low variance (sweet spot)"
    else:
        interp = "← reasonable"

    print(f"  {one_line_name:<40} {mean_score:>8.3f} {std_score:>8.3f}  {interp}")

print("\nReading this table:")
print("  Mean F1  = how well the model performs on average (bias indicator)")
print("  Std Dev  = how much scores vary across the 5 folds (variance indicator)")
print("  Low mean → high bias (model can't learn the patterns)")
print("  High std → high variance (model is too sensitive to which data it sees)")
print("  We want: high mean AND low std → the sweet spot")

print(DIVIDER)
print("SUMMARY — All concepts covered:")
print(DIVIDER)
print("  ✓ Supervised learning    → logistic regression, decision tree, random forest")
print("  ✓ Unsupervised learning  → k-means clustering")
print(
    "  ✓ Labels                 → what you teach the model; come from historical data"
)
print("  ✓ Train/val/test split   → 60/20/20; test set touched exactly once")
print("  ✓ Class imbalance        → why accuracy is misleading; use F1 / AUC instead")
print("  ✓ Confusion matrix       → TP, TN, FP, FN — foundation of all metrics")
print("  ✓ Precision              → of what you flagged, how many were real")
print("  ✓ Recall                 → of all real positives, how many you caught")
print("  ✓ F1                     → harmonic mean; use when both P and R matter")
print("  ✓ AUC-ROC                → threshold-independent model quality; 0.5=random")
print("  ✓ RMSE / MAE             → regression metrics; RMSE penalizes big errors more")
print(
    "  ✓ Overfitting            → memorizes training data; train/test gap is the signal"
)
print("  ✓ Underfitting           → too simple; poor on both train and test")
print("  ✓ Regularization         → max_depth, class_weight — controls overfitting")
print(
    "  ✓ Bias-variance tradeoff → simple=high bias; complex=high variance; find the middle"
)
print(
    "  ✓ Cross-validation       → 5-fold; reliable performance estimate with limited data"
)
print("  ✓ Elbow method           → how to choose k in k-means")
print(
    "  ✓ Feature importance     → random forest bonus: tells you which inputs matter most"
)
print()
print("Charts saved in ml-fundamentals/:")
print("  overfit_curve.png  — training vs test accuracy by tree depth")
print("  roc_curve.png      — ROC curves for both classifiers")
print("  kmeans.png         — cluster plot + elbow curve")
