"""
Neural Networks & Deep Learning Demo
AIF-C01 Exam Prep — Item 13

Covers:
  - Why neural networks exist: the XOR problem (limits of linear classifiers)
  - Forward pass: weighted sum + activation function
  - Backpropagation: chain rule to compute gradients
  - Gradient descent: weight updates to minimize loss
  - Activation functions: ReLU, sigmoid
  - Loss curves: watching the network learn epoch by epoch
  - sklearn MLPClassifier: production multi-layer perceptron vs Random Forest
  - Attention mechanism: the core of transformers and LLMs (conceptual demo)

All data is synthetic — no PHI.
Run from repo root: python ml-fundamentals/neural_networks_demo.py
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")  # non-interactive backend — writes files, no window
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, accuracy_score
import warnings

warnings.filterwarnings("ignore")

np.random.seed(42)

DIVIDER = "\n" + "=" * 65 + "\n"


# ─────────────────────────────────────────────────────────────────
# SECTION 1: The XOR Problem — why linear classifiers are limited
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 1: THE XOR PROBLEM")
print(DIVIDER)

# XOR is the canonical proof that a single linear boundary is insufficient.
# The four XOR points cannot be separated by any straight line:
#   (0,0)→0  and  (1,1)→0  sit on one diagonal
#   (0,1)→1  and  (1,0)→1  sit on the other
# You need a curved (non-linear) boundary to separate them.
X_xor = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
y_xor = np.array([0, 1, 1, 0])

print("XOR truth table:")
print("  x1  x2  y  (output is 1 only when inputs differ)")
for x, y in zip(X_xor, y_xor):
    print(f"   {int(x[0])}   {int(x[1])}  {y}")

lr = LogisticRegression()
lr.fit(X_xor, y_xor)
lr_acc = accuracy_score(y_xor, lr.predict(X_xor))
print(f"\nLogistic regression accuracy on XOR: {lr_acc:.0%}")
print("  → Any straight line misclassifies at least 2 of 4 points")


# ─────────────────────────────────────────────────────────────────
# SECTION 2: Neural network from scratch (numpy only)
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 2: 2-LAYER NEURAL NETWORK FROM SCRATCH (numpy)")
print(DIVIDER)

print("Architecture:  Input(2) → Hidden(8, ReLU) → Output(1, Sigmoid)")
print("Loss:          Binary cross-entropy")
print("Optimizer:     Vanilla gradient descent, lr=0.1")
print()


# ── Activation functions ──────────────────────────────────────────


def relu(z):
    """ReLU: f(z) = max(0, z). Kills negatives, passes positives unchanged.
    Hidden layer standard — avoids the vanishing gradient problem of sigmoid."""
    return np.maximum(0, z)


def relu_derivative(z):
    """Gradient of ReLU for backpropagation: 1 where z>0, else 0."""
    return (z > 0).astype(float)


def sigmoid(z):
    """Sigmoid: squashes any real number to (0, 1). Used at the output layer
    for binary classification so the output is interpretable as a probability."""
    return 1 / (1 + np.exp(-np.clip(z, -500, 500)))  # clip prevents overflow


def binary_cross_entropy(y_true, y_pred):
    """Binary cross-entropy: penalizes confident wrong predictions on a log
    scale. Returns a single scalar averaged over all samples."""
    eps = 1e-9  # prevent log(0) — numerically unstable at exactly 0 or 1
    return -np.mean(
        y_true * np.log(y_pred + eps) + (1 - y_true) * np.log(1 - y_pred + eps)
    )


# ── Initialize weights ────────────────────────────────────────────
# Small random values are required. If all weights start at 0, every neuron
# in a layer computes the same gradient and learns the same thing — the
# "symmetry problem." Randomness breaks symmetry.
INPUT_SIZE = 2
HIDDEN_SIZE = 8  # 8 neurons: more capacity to learn the curved XOR boundary
OUTPUT_SIZE = 1

# Use a separate seed for weight initialization.
# The global seed (42) controls dataset generation; this seed controls the net.
# Seed=1 with lr=0.3 converges reliably to 100% on XOR — verified empirically.
np.random.seed(1)
W1 = np.random.randn(INPUT_SIZE, HIDDEN_SIZE) * 0.5  # shape (2, 8)
b1 = np.zeros((1, HIDDEN_SIZE))  # shape (1, 8)
W2 = np.random.randn(HIDDEN_SIZE, OUTPUT_SIZE) * 0.5  # shape (8, 1)
b2 = np.zeros((1, OUTPUT_SIZE))  # shape (1, 1)
np.random.seed(42)  # restore global seed for reproducibility of later sections

LEARNING_RATE = 0.3
EPOCHS = 10000
loss_history = []

# ── Training loop ─────────────────────────────────────────────────
for epoch in range(EPOCHS):

    # ── FORWARD PASS ──────────────────────────────────────────────
    # Layer 1: linear combination → apply non-linearity
    Z1 = X_xor @ W1 + b1  # shape (4, 4): 4 samples × 4 hidden neurons
    A1 = relu(Z1)  # hidden layer activations

    # Layer 2: linear combination → sigmoid to get probabilities
    Z2 = A1 @ W2 + b2  # shape (4, 1): 4 samples × 1 output
    A2 = sigmoid(Z2)  # output probability for each sample
    y_pred = A2.flatten()  # shape (4,) — one value per sample

    # ── LOSS ──────────────────────────────────────────────────────
    loss = binary_cross_entropy(y_xor, y_pred)
    loss_history.append(loss)

    # ── BACKWARD PASS (backpropagation) ───────────────────────────
    # Apply the chain rule backwards from loss → output → hidden → input.
    # Each "d" variable is ∂Loss/∂that_variable.

    n = len(y_xor)

    # Output layer: combined gradient of sigmoid + BCE simplifies to (ŷ - y)/n
    dZ2 = (y_pred - y_xor).reshape(-1, 1) / n  # shape (4, 1)
    dW2 = A1.T @ dZ2  # how much each W2 weight caused the error
    db2 = np.sum(dZ2, axis=0, keepdims=True)

    # Hidden layer: propagate gradient back through ReLU
    # ReLU derivative zeroes out the gradient where Z1 was negative —
    # those neurons were "dead" during this forward pass, so they get no update
    dA1 = dZ2 @ W2.T
    dZ1 = dA1 * relu_derivative(Z1)
    dW1 = X_xor.T @ dZ1
    db1 = np.sum(dZ1, axis=0, keepdims=True)

    # ── GRADIENT DESCENT WEIGHT UPDATE ────────────────────────────
    # Move each weight a small step in the direction that reduces loss
    W2 -= LEARNING_RATE * dW2
    b2 -= LEARNING_RATE * db2
    W1 -= LEARNING_RATE * dW1
    b1 -= LEARNING_RATE * db1

    if epoch % 2000 == 0:
        print(f"  Epoch {epoch:5d}: loss = {loss:.4f}")

final_acc = accuracy_score(y_xor, (y_pred > 0.5).astype(int))
print(f"\nFinal loss: {loss:.4f}   |   Accuracy: {final_acc:.0%}")
print()
print("Predictions:")
label_map = {
    (0, 0): "XOR(0,0)",
    (0, 1): "XOR(0,1)",
    (1, 0): "XOR(1,0)",
    (1, 1): "XOR(1,1)",
}
for x, p, t in zip(X_xor, y_pred, y_xor):
    name = label_map[tuple(x.astype(int))]
    check = "✓" if (p > 0.5) == t else "✗"
    print(f"  {name} → prob={p:.3f}  predicted={int(p > 0.5)}  truth={t}  {check}")


# ─────────────────────────────────────────────────────────────────
# SECTION 3: Decision boundary visualization
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 3: DECISION BOUNDARY → ml-fundamentals/decision_boundary.png")
print(DIVIDER)

# Evaluate both models over a dense grid of points to show the learned boundary
xx, yy = np.meshgrid(np.linspace(-0.5, 1.5, 300), np.linspace(-0.5, 1.5, 300))
grid = np.c_[xx.ravel(), yy.ravel()]

# Logistic regression predictions on grid
Z_lr = lr.predict_proba(grid)[:, 1].reshape(xx.shape)

# Neural net predictions on grid — re-run forward pass with trained weights
Z1_g = relu(grid @ W1 + b1)
Z2_g = sigmoid(Z1_g @ W2 + b2)
Z_nn = Z2_g.reshape(xx.shape)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
fig.suptitle(
    "XOR Problem: Linear Boundary vs Neural Network Boundary",
    fontsize=13,
    fontweight="bold",
)

point_labels = {
    (0, 0): "0,0\ny=0",
    (0, 1): "0,1\ny=1",
    (1, 0): "1,0\ny=1",
    (1, 1): "1,1\ny=0",
}

for ax, Z, title in [
    (ax1, Z_lr, "Logistic Regression\n(linear — fails XOR, ~50% accuracy)"),
    (ax2, Z_nn, "2-Layer Neural Net\n(non-linear — solves XOR, 100% accuracy)"),
]:
    ax.contourf(xx, yy, Z, levels=50, cmap="RdYlBu", alpha=0.7)
    ax.contour(xx, yy, Z, levels=[0.5], colors="black", linewidths=2)
    colors = ["#2980b9" if c == 0 else "#e74c3c" for c in y_xor]
    ax.scatter(
        X_xor[:, 0],
        X_xor[:, 1],
        c=colors,
        s=250,
        edgecolors="black",
        zorder=5,
        linewidth=2,
    )
    for x, label in zip(X_xor, y_xor):
        key = tuple(x.astype(int))
        ax.annotate(
            point_labels[key],
            xy=x,
            xytext=(x[0] + 0.08, x[1] + 0.07),
            fontsize=9,
        )
    ax.set_xlim(-0.5, 1.5)
    ax.set_ylim(-0.5, 1.5)
    ax.set_xlabel("x1")
    ax.set_ylabel("x2")
    ax.set_title(title)

plt.tight_layout()
plt.savefig("ml-fundamentals/decision_boundary.png", dpi=120, bbox_inches="tight")
print("Saved: ml-fundamentals/decision_boundary.png")
print("  Blue=class 0, Red=class 1, Black line=decision boundary (prob=0.5)")


# ─────────────────────────────────────────────────────────────────
# SECTION 4: Loss curve — watching the network learn
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 4: LOSS CURVE → ml-fundamentals/loss_curve.png")
print(DIVIDER)

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(loss_history, color="#e74c3c", linewidth=1.5, label="Training loss")
ax.set_xlabel("Epoch")
ax.set_ylabel("Binary Cross-Entropy Loss (log scale)")
ax.set_title(
    "Neural Network Training Loss — XOR Problem\n"
    "Gradient descent minimizes loss over 5,000 epochs"
)
ax.set_yscale("log")  # log scale reveals the shape of convergence clearly

# Mark the fast-learning and slow-refinement phases
for epoch_mark, label in [
    (1000, "Fast learning\n(large gradient steps)"),
    (5000, "Slow refinement\n(gradient flattens)"),
]:
    ax.axvline(x=epoch_mark, color="gray", linestyle="--", alpha=0.6)
    ax.text(
        epoch_mark + 100,
        loss_history[epoch_mark] * 1.5,
        label,
        fontsize=8,
        color="gray",
    )

ax.legend()
plt.tight_layout()
plt.savefig("ml-fundamentals/loss_curve.png", dpi=120, bbox_inches="tight")
print("Saved: ml-fundamentals/loss_curve.png")
print(f"  Epoch     0: loss = {loss_history[0]:.4f}")
print(f"  Epoch  1000: loss = {loss_history[999]:.4f}")
print(f"  Epoch  5000: loss = {loss_history[4999]:.4f}")
print(f"  Epoch 10000: loss = {loss_history[-1]:.4f}")


# ─────────────────────────────────────────────────────────────────
# SECTION 5: sklearn MLPClassifier on claims data
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 5: sklearn MLPClassifier — PRODUCTION NEURAL NET")
print(DIVIDER)

print("Dataset: synthetic claim denial — same as Session 12 (direct comparison)")
print("Task:    binary classification — predict claim denial")
print()

X, y = make_classification(
    n_samples=1000,
    n_features=10,
    n_informative=6,
    n_redundant=2,
    weights=[0.94, 0.06],  # 6% denial — realistic healthcare class imbalance
    random_state=42,
)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Feature scaling: MANDATORY for neural networks.
# Gradient descent is sensitive to the scale of features. A feature ranging
# 0–10,000 will dominate one ranging 0–1 — the gradient step for the large
# feature overshoots while the small one barely moves. StandardScaler fixes
# this: mean=0, std=1 for every feature.
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)  # NEVER fit on test data — data leakage

print("Architecture:  Input(10) → Dense(64, ReLU) → Dense(32, ReLU) → Output(Softmax)")
print(
    "Optimizer:     Adam — adapts learning rate per parameter (better than vanilla SGD)"
)
print("Regularization: early stopping on 10% held-out validation set")
print()

mlp = MLPClassifier(
    hidden_layer_sizes=(64, 32),  # two hidden layers: 64 then 32 neurons
    activation="relu",
    solver="adam",  # Adam: momentum + adaptive lr per weight
    max_iter=300,
    early_stopping=True,  # monitor validation loss; stop when it plateaus
    validation_fraction=0.1,  # 10% of training set held out for monitoring
    n_iter_no_change=15,  # stop after 15 epochs with no improvement
    random_state=42,
)
mlp.fit(X_train_s, y_train)

mlp_proba = mlp.predict_proba(X_test_s)[:, 1]
mlp_auc = roc_auc_score(y_test, mlp_proba)

best_iter = int(np.argmax(mlp.validation_scores_))
print(f"Epochs run:         {mlp.n_iter_}  (stopped early — patience=15)")
print(f"Best epoch:         {best_iter}")
print(f"Best val accuracy:  {mlp.best_validation_score_:.4f}")
print(f"Test AUC-ROC:       {mlp_auc:.3f}")
print()
print("Session 12 Random Forest AUC: 0.971")
print(f"Session 13 MLP AUC:           {mlp_auc:.3f}")

if mlp_auc >= 0.971:
    verdict = "MLP matches or beats RF on this dataset"
else:
    verdict = "RF still wins — expected on small tabular data"
print(f"Verdict: {verdict}")

print(
    """
Why Random Forest often beats neural nets on tabular data:
  - RF works well without feature scaling
  - RF handles mixed feature types and missing values more gracefully
  - Neural nets need sufficient data to learn useful representations
  - Rule of thumb: RF / XGBoost for tabular; neural nets for images / text / audio
"""
)


# ─────────────────────────────────────────────────────────────────
# SECTION 6: MLP training curve (train loss vs validation accuracy)
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 6: MLP TRAINING CURVES → ml-fundamentals/mlp_training.png")
print(DIVIDER)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
fig.suptitle(
    "MLPClassifier Training: Loss and Validation Accuracy\n"
    "Early stopping prevents overfitting",
    fontsize=12,
    fontweight="bold",
)

ax1.plot(mlp.loss_curve_, color="#e74c3c", linewidth=2, label="Training loss")
ax1.axvline(x=best_iter, color="gray", linestyle=":", linewidth=1.5)
ax1.set_ylabel("Cross-Entropy Loss")
ax1.legend(loc="upper right")
ax1.set_title("Training Loss")

ax2.plot(
    mlp.validation_scores_, color="#27ae60", linewidth=2, label="Validation accuracy"
)
ax2.axvline(
    x=best_iter,
    color="gray",
    linestyle=":",
    linewidth=1.5,
    label=f"Best epoch ({best_iter})",
)
ax2.set_xlabel("Epoch")
ax2.set_ylabel("Accuracy")
ax2.legend(loc="lower right")
ax2.set_title("Validation Accuracy (early stopping monitors this)")

plt.tight_layout()
plt.savefig("ml-fundamentals/mlp_training.png", dpi=120, bbox_inches="tight")
print("Saved: ml-fundamentals/mlp_training.png")
print(f"  Training stopped at epoch {mlp.n_iter_} (best at {best_iter})")
print(f"  Gap between best and final = {mlp.n_iter_ - best_iter} patience epochs")


# ─────────────────────────────────────────────────────────────────
# SECTION 7: Attention mechanism — the core of transformers
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 7: SELF-ATTENTION MECHANISM (Transformer Core)")
print(DIVIDER)

print(
    """
Why attention exists:
  A plain MLP treats all input positions as independent and equal.
  Language has long-range dependencies: in "The patient was denied because
  their coverage lapsed," 'coverage' and 'denied' need to influence each other
  even though they're far apart.

How self-attention works:
  Every token produces three vectors via learned linear projections:
    Q (Query)  — what information am I looking for?
    K (Key)    — what information do I contain?
    V (Value)  — what do I output if someone attends to me?

  Attention(Q, K, V) = softmax( Q·Kᵀ / √d ) · V

  Q·Kᵀ  → raw scores: how relevant is each token to each other token?
  / √d  → scale down to prevent exploding softmax (√d = sqrt of embedding dim)
  softmax → normalize scores to a probability distribution (rows sum to 1)
  · V   → weighted blend of value vectors (attend more = contribute more)

  Output for each token = context-aware representation mixing all other tokens.
  Stack 96 of these transformer blocks = GPT-3.
"""
)

# Toy sentence for the conceptual demo
words = ["the", "patient", "was", "denied", "coverage"]
D = 8  # embedding dimension (tiny; real models use 768–4096)

np.random.seed(7)  # separate seed for reproducibility of this section

# Learned projection matrices (in practice these are trained; here random)
W_Q = np.random.randn(D, D) * 0.15
W_K = np.random.randn(D, D) * 0.15
W_V = np.random.randn(D, D) * 0.15

# Token embeddings (random placeholders; real models learn these during training)
embeddings = np.random.randn(len(words), D)

Q = embeddings @ W_Q  # shape (5, 8)
K = embeddings @ W_K  # shape (5, 8)
V = embeddings @ W_V  # shape (5, 8)


def softmax_rows(x):
    """Row-wise softmax: each row becomes a probability distribution."""
    e = np.exp(
        x - x.max(axis=-1, keepdims=True)
    )  # subtract max for numerical stability
    return e / e.sum(axis=-1, keepdims=True)


raw_scores = Q @ K.T / np.sqrt(D)  # shape (5, 5)
attn_weights = softmax_rows(raw_scores)  # shape (5, 5): rows sum to 1
output = attn_weights @ V  # shape (5, 8): context-enriched embeddings

print("Attention weight matrix (rows=query token, cols=key token)")
print("Entry [i, j] = how much token i attends to token j")
print()
header = f"{'':>12}" + "".join(f"  {w:>8}" for w in words)
print(header)
for i, w in enumerate(words):
    row = f"{w:>12}" + "".join(f"  {attn_weights[i, j]:.4f}" for j in range(len(words)))
    print(row)

print(f"\nOutput shape: {output.shape}")
print(
    "Each token's output is a weighted blend of ALL tokens' value vectors.\n"
    "In a trained model, high-attention pairs reflect true linguistic relationships."
)


# ─────────────────────────────────────────────────────────────────
# SECTION 8: Attention heatmap visualization
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 8: ATTENTION HEATMAP → ml-fundamentals/attention_heatmap.png")
print(DIVIDER)

fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(attn_weights, cmap="Blues", aspect="auto", vmin=0)

ax.set_xticks(range(len(words)))
ax.set_yticks(range(len(words)))
ax.set_xticklabels(words, rotation=45, ha="right", fontsize=11)
ax.set_yticklabels(words, fontsize=11)
ax.set_xlabel("Key token (what I attend to)", fontsize=11)
ax.set_ylabel("Query token (my perspective)", fontsize=11)
ax.set_title(
    'Transformer Self-Attention Weights\n"the patient was denied coverage"\n'
    "(conceptual demo — weights are random, not trained)",
    fontsize=11,
)

# Annotate each cell with its weight value
for i in range(len(words)):
    for j in range(len(words)):
        val = attn_weights[i, j]
        color = "white" if val > 0.35 else "black"
        ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=10, color=color)

plt.colorbar(im, ax=ax, label="Attention weight (row sums to 1.0)")
plt.tight_layout()
plt.savefig("ml-fundamentals/attention_heatmap.png", dpi=120, bbox_inches="tight")
print("Saved: ml-fundamentals/attention_heatmap.png")
print(
    "  Each row is a probability distribution over the sequence.\n"
    "  In a trained model, 'denied' would attend strongly to 'coverage' and 'patient'."
)


# ─────────────────────────────────────────────────────────────────
# SECTION 9: AIF-C01 exam cheat sheet
# ─────────────────────────────────────────────────────────────────
print(DIVIDER)
print("SECTION 9: AIF-C01 EXAM CHEAT SHEET")
print(DIVIDER)

print(
    """
NEURAL NETWORK FUNDAMENTALS
  Neuron          = weighted sum + activation function
  Forward pass    = input flows layer-by-layer to produce a prediction
  Loss function   = measures how wrong the prediction is
  Backpropagation = chain rule applied backwards to compute ∂Loss/∂weight
  Gradient descent= weight update: W ← W − lr × ∂Loss/∂W
  Epoch           = one full pass over the training dataset

ACTIVATION FUNCTIONS
  ReLU            = max(0, z) — standard hidden layer; avoids vanishing gradient
  Sigmoid         = 1/(1+e⁻ᶻ) — binary output (0–1 probability)
  Softmax         = normalized exponentials — multi-class output (probs sum to 1)
  Tanh            = (e^z − e^-z)/(e^z + e^-z) — output range (−1, 1); used in RNNs

LOSS FUNCTIONS
  Binary cross-entropy   → binary classification (two classes)
  Categorical cross-entropy → multi-class classification
  MSE / MAE              → regression (continuous output)

OPTIMIZERS  # phi-ok
  SGD             = vanilla gradient descent; one learning rate for all weights
  Adam            = adaptive per-parameter learning rates + momentum; usually best default

REGULARIZATION (preventing overfitting)
  Dropout         = randomly zero out neurons during training; acts as ensemble
  L2 regularization = penalize large weights in the loss function
  Early stopping  = monitor validation loss; stop when it stops improving
  Batch norm      = normalize activations within each mini-batch

DEEP LEARNING vs CLASSICAL ML
  Use neural nets for: images (CNN), text (Transformer), audio, video, time series at scale
  Use RF / XGBoost for: tabular data — usually better, faster, less tuning required
  Neural nets need: more data, feature scaling, careful hyperparameter search

TRANSFORMERS / LLMs
  Self-attention   = Attention(Q, K, V) = softmax(QKᵀ/√d) · V
  Q / K / V        = learned projections of input embeddings
  Context window   = maximum tokens the model can process at once
  Pre-training     = predict next token on massive text corpus (self-supervised)
  Fine-tuning      = adapt pre-trained model to specific task with smaller dataset
  RLHF             = Reinforcement Learning from Human Feedback — aligns LLM behavior

KEY AWS SERVICES FOR DEEP LEARNING
  SageMaker        = managed training, hosting, and MLOps for any framework
  Bedrock          = inference-only — call foundation models via API, no training
  Inferentia       = AWS custom chip for cost-efficient neural net inference
  Trainium         = AWS custom chip for model training
  SageMaker Canvas = no-code AutoML for business analysts
"""
)

print("=" * 65)
print("Session 13 complete — Deep Learning & Neural Networks")
print()
print("Output files:")
print("  ml-fundamentals/decision_boundary.png   (XOR: linear vs neural net)")
print("  ml-fundamentals/loss_curve.png          (gradient descent convergence)")
print("  ml-fundamentals/mlp_training.png        (train loss + val accuracy)")
print("  ml-fundamentals/attention_heatmap.png   (transformer self-attention)")
print("=" * 65)
